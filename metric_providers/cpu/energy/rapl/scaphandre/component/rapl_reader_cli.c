/*
 * rapl_reader_cli.c
 *
 * Windows CLI tool that reads RAPL MSR values directly from the
 * ScaphandreDrv kernel driver and outputs them in GMT format to stdout.
 *
 * Output format (GMT standard):
 *   timestamp_microseconds value detail_name
 *   1774007770584099 3614000000 cpu_package
 *
 * Unit: uJ (micro-Joules) to avoid GMT resolution underflow
 * (GMT raises error if value <= 1 for mJ/uJ units)
 *
 * Timing: QueryPerformanceCounter (monotonic, ~100ns resolution)
 * + wall-clock offset at startup. Immune to DST and leap seconds.
 * Mirrors GMT's gmt-lib.c get_time_offset() / get_adjusted_time().
 *
 * Usage:
 *   rapl_reader.exe -i <interval_ms>        (default: 99ms)
 *   rapl_reader.exe -i 99 -d cpu_package    (single domain)
 *   rapl_reader.exe -c                      (check mode)
 *
 * Available domains: cpu_package, cpu_cores, cpu_gpu, dram
 * Default: all supported domains (DRAM auto-detected at startup)
 *
 * Build (x64 Native Tools Command Prompt for VS 2022):
 *   cl rapl_reader_cli.c /Fe:rapl_reader.exe /O2 /W3
 */

#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>

/* ── Device path ─────────────────────────────────────────── */
#define DEVICE_PATH "\\\\.\\ScaphandreDriver"

/* ── IOCTL code ───────────────────────────────────────────── */
#define IOCTL_READ_MSR CTL_CODE(FILE_DEVICE_UNKNOWN, 0x800, METHOD_BUFFERED, FILE_ANY_ACCESS)

/* ── MSR Register addresses ───────────────────────────────── */
#define MSR_RAPL_POWER_UNIT        0x00000606
#define MSR_PKG_ENERGY_STATUS      0x00000611
#define MSR_DRAM_ENERGY_STATUS     0x00000619
#define MSR_PP0_ENERGY_STATUS      0x00000639
#define MSR_PP1_ENERGY_STATUS      0x00000641
#define MSR_AMD_RAPL_POWER_UNIT    0xc0010299
#define MSR_AMD_PKG_ENERGY_STATUS  0xc001029b
#define MSR_AMD_CORE_ENERGY_STATUS 0xc001029a

/* ── Domain flags ─────────────────────────────────────────── */
#define DOMAIN_PKG   (1 << 0)
#define DOMAIN_CORES (1 << 1)
#define DOMAIN_GPU   (1 << 2)
#define DOMAIN_DRAM  (1 << 3)
#define DOMAIN_ALL   (DOMAIN_PKG | DOMAIN_CORES | DOMAIN_GPU | DOMAIN_DRAM)

/* ── Structs ──────────────────────────────────────────────── */
#pragma pack(push, 1)
typedef struct { uint32_t msrRegister; uint32_t cpuIndex; } msr_request_t;
#pragma pack(pop)

typedef struct {
    double pkg_energy_j;
    double dram_energy_j;
    double pp0_energy_j;
    double pp1_energy_j;
    int    valid;
} rapl_sample_t;

/* ── Monotonic clock state ────────────────────────────────── */
typedef struct {
    LARGE_INTEGER qpc_start;
    uint64_t      wall_start_us;
    double        qpc_freq_us;
} clock_state_t;

/* ── parse_int() ──────────────────────────────────────────── */
/*
 * Mirrors GMT's gmt-lib.c parse_int() - robust integer parsing
 * using strtoul instead of atoi to handle edge cases correctly.
 */
static unsigned int parse_int(char *argument)
{
    unsigned long number = 0;
    char *endptr;
    errno = 0;
    number = strtoul(argument, &endptr, 10);
    if (errno == ERANGE && (number == ULONG_MAX || number == 0)) {
        fprintf(stderr, "Error: Could not parse -i argument - Number out of range\n");
        exit(1);
    } else if (errno != 0 && number == 0) {
        fprintf(stderr, "Error: Could not parse -i argument - Invalid number\n");
        exit(1);
    } else if (endptr == argument) {
        fprintf(stderr, "Error: Could not parse -i argument - No digits were found\n");
        exit(1);
    } else if (*endptr != '\0') {
        fprintf(stderr, "Error: Could not parse -i argument - Invalid characters after number\n");
        exit(1);
    }
    return (unsigned int)number;
}

/* ── Clock helpers ────────────────────────────────────────── */

static uint64_t get_wall_time_us(void)
{
    FILETIME ft;
    GetSystemTimeAsFileTime(&ft);
    uint64_t t = ((uint64_t)ft.dwHighDateTime << 32) | ft.dwLowDateTime;
    return (t - 116444736000000000ULL) / 10;
}

/*
 * clock_init() - mirrors GMT's get_time_offset()
 * Records wall-clock and QPC at startup to anchor monotonic clock.
 */
static clock_state_t clock_init(void)
{
    clock_state_t cs;
    LARGE_INTEGER freq;
    QueryPerformanceFrequency(&freq);
    cs.qpc_freq_us   = (double)freq.QuadPart / 1000000.0;
    cs.wall_start_us = get_wall_time_us();
    QueryPerformanceCounter(&cs.qpc_start);
    return cs;
}

/*
 * now_us() - mirrors GMT's get_adjusted_time()
 * Returns Unix epoch microseconds using monotonic QPC + startup offset.
 * Immune to DST changes and leap seconds.
 */
static uint64_t now_us(const clock_state_t *cs)
{
    LARGE_INTEGER qpc_now;
    QueryPerformanceCounter(&qpc_now);
    double elapsed_us = (double)(qpc_now.QuadPart - cs->qpc_start.QuadPart)
                        / cs->qpc_freq_us;
    return cs->wall_start_us + (uint64_t)elapsed_us;
}

/* ── Driver helpers ───────────────────────────────────────── */

static HANDLE open_driver(void)
{
    return CreateFileA(DEVICE_PATH, GENERIC_READ | GENERIC_WRITE, 0, NULL,
                       OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
}

static int read_msr(HANDLE hDev, uint32_t reg, uint32_t cpu, uint64_t *out)
{
    msr_request_t req = { reg, cpu };
    DWORD bytes = 0;
    BOOL ok = DeviceIoControl(hDev, IOCTL_READ_MSR,
                               &req, sizeof(req),
                               out,  sizeof(*out),
                               &bytes, NULL);
    return (ok && bytes >= sizeof(uint64_t)) ? 0 : -1;
}

/* ── Read energy unit ONCE at startup ─────────────────────── */
/*
 * The power unit register does not change during operation.
 * Read once at startup to reduce per-sample IOCTL overhead.
 */
static double read_energy_unit(HANDLE hDev, uint32_t cpu)
{
    uint64_t raw = 0;
    if (read_msr(hDev, MSR_RAPL_POWER_UNIT, cpu, &raw) != 0)
        if (read_msr(hDev, MSR_AMD_RAPL_POWER_UNIT, cpu, &raw) != 0)
            return -1.0;
    return 1.0 / (double)(1ULL << ((raw >> 8) & 0x1F));
}

/* ── DRAM domain auto-detection ───────────────────────────── */
/*
 * Check at startup whether DRAM energy reporting is supported.
 * Takes two readings 100ms apart - if the counter never changes,
 * DRAM is not supported on this CPU and will be excluded.
 * This avoids GMT's resolution underflow error (value <= 1).
 */
static int is_domain_active(HANDLE hDev, uint32_t cpu,
                             uint32_t msr_reg, double energy_unit,
                             int samples, int interval_ms)
{
    uint64_t prev = 0, curr = 0;
    int zero_count = 0;

    if (read_msr(hDev, msr_reg, cpu, &prev) != 0)
        return 0; /* MSR not accessible */

    for (int i = 0; i < samples; i++) {
        Sleep(interval_ms);

        if (read_msr(hDev, msr_reg, cpu, &curr) != 0)
            return 0;

        double delta = ((double)(curr & 0xFFFFFFFF) - (double)(prev & 0xFFFFFFFF))
                       * energy_unit;

        /* Handle wrap-around */
        if (delta < 0) delta += (double)(1ULL << 32) * energy_unit;

        long long uj = (long long)(delta * 1000000.0);
        if (uj <= 1) zero_count++;

        prev = curr;
    }

    /* Domain inactive if ALL samples were <= 1 uJ */
    return (zero_count < samples) ? 1 : 0;
}

/* ── Read energy sample ───────────────────────────────────── */
static rapl_sample_t read_rapl(HANDLE hDev, uint32_t cpu,
                                double energy_unit, int domains)
{
    rapl_sample_t s = {0};
    uint64_t raw = 0;

    if (domains & DOMAIN_PKG)
        if (read_msr(hDev, MSR_PKG_ENERGY_STATUS, cpu, &raw) == 0)
            s.pkg_energy_j = (raw & 0xFFFFFFFF) * energy_unit;

    if (domains & DOMAIN_DRAM)
        if (read_msr(hDev, MSR_DRAM_ENERGY_STATUS, cpu, &raw) == 0)
            s.dram_energy_j = (raw & 0xFFFFFFFF) * energy_unit;

    if (domains & DOMAIN_CORES)
        if (read_msr(hDev, MSR_PP0_ENERGY_STATUS, cpu, &raw) == 0)
            s.pp0_energy_j = (raw & 0xFFFFFFFF) * energy_unit;

    if (domains & DOMAIN_GPU)
        if (read_msr(hDev, MSR_PP1_ENERGY_STATUS, cpu, &raw) == 0)
            s.pp1_energy_j = (raw & 0xFFFFFFFF) * energy_unit;

    s.valid = 1;
    return s;
}

/* ── Delta with 32-bit wrap-around correction ─────────────── */
/*
 * Returns delta in micro-Joules (uJ).
 * Only negative values (overflow edge cases) are skipped,
 * matching GMT's native RAPL provider (source.c line 478:
 * if energy_output >= 0).
 */
static long long delta_uj(double curr, double prev, double eu)
{
    double d = curr - prev;
    if (d < 0) d += (double)(1ULL << 32) * eu;
    return (long long)(d * 1000000.0);
}

/* ── Parse domain string ──────────────────────────────────── */
static int parse_domain(const char *d)
{
    if (!strcmp(d, "cpu_package")) return DOMAIN_PKG;
    if (!strcmp(d, "cpu_cores"))   return DOMAIN_CORES;
    if (!strcmp(d, "cpu_gpu"))     return DOMAIN_GPU;
    if (!strcmp(d, "dram"))        return DOMAIN_DRAM;
    fprintf(stderr, "Error: Unknown domain '%s'. "
            "Valid: cpu_package, cpu_cores, cpu_gpu, dram\n", d);
    exit(1);
}

/* ── Main ─────────────────────────────────────────────────── */
int main(int argc, char *argv[])
{
    unsigned int interval_ms = 99;
    int check_mode   = 0;
    int domains      = DOMAIN_ALL;
    int user_domains = 0; /* 1 if user explicitly set domains via -d */

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-i") && i + 1 < argc)
            interval_ms = parse_int(argv[++i]);
        else if (!strcmp(argv[i], "-d") && i + 1 < argc) {
            domains      = parse_domain(argv[++i]);
            user_domains = 1;
        }
        else if (!strcmp(argv[i], "-c"))
            check_mode = 1;
    }

    HANDLE hDev = open_driver();
    if (hDev == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "Cannot open driver. Error: %lu\n", GetLastError());
        return 1;
    }

    /* Check mode: verify driver is accessible */
    if (check_mode) {
        double eu = read_energy_unit(hDev, 0);
        CloseHandle(hDev);
        return (eu > 0) ? 0 : 1;
    }

    /* Read energy unit ONCE at startup (does not change) */
    double energy_unit = read_energy_unit(hDev, 0);
    if (energy_unit <= 0) {
        fprintf(stderr, "Cannot read RAPL power unit MSR.\n");
        CloseHandle(hDev);
        return 1;
    }

    /*
     * Auto-detect supported domains (only if user did not explicitly
     * specify domains via -d flag).
     * DRAM is not supported on all CPUs - check before starting
     * to avoid GMT resolution underflow errors (value = 0).
     */
if (!user_domains) {
    if (!is_domain_active(hDev, 0, MSR_DRAM_ENERGY_STATUS, energy_unit, 5, 100)) {
        domains &= ~DOMAIN_DRAM;
        fprintf(stderr, "Info: DRAM domain not supported on this CPU, disabling.\n");
    }
    if (!is_domain_active(hDev, 0, MSR_PP1_ENERGY_STATUS, energy_unit, 5, 100)) {
        domains &= ~DOMAIN_GPU;
        fprintf(stderr, "Info: GPU domain not supported on this CPU, disabling.\n");
    }
}
    /* Disable stdout buffering so GMT reads data immediately */
    setvbuf(stdout, NULL, _IONBF, 0);

    /* Initialize monotonic clock (mirrors GMT's get_time_offset) */
    clock_state_t cs = clock_init();

    rapl_sample_t prev = {0};
    int first = 1;

    while (1) {
        rapl_sample_t curr = read_rapl(hDev, 0, energy_unit, domains);
        uint64_t ts = now_us(&cs);

        if (curr.valid && !first) {
            long long pkg_uj  = delta_uj(curr.pkg_energy_j,  prev.pkg_energy_j,  energy_unit);
            long long pp0_uj  = delta_uj(curr.pp0_energy_j,  prev.pp0_energy_j,  energy_unit);
            long long pp1_uj  = delta_uj(curr.pp1_energy_j,  prev.pp1_energy_j,  energy_unit);
            long long dram_uj = delta_uj(curr.dram_energy_j, prev.dram_energy_j, energy_unit);

            /*
             * Only skip negative values (overflow edge cases).
             * Matches GMT's native RAPL provider behavior.
             * Use +1us timestamp offsets per domain so GMT can
             * calculate per-domain sampling rates correctly.
             */
            if ((domains & DOMAIN_PKG)   && pkg_uj  >= 0)
                printf("%llu %lld cpu_package\n", (unsigned long long)ts,     pkg_uj);
            if ((domains & DOMAIN_CORES) && pp0_uj  >= 0)
                printf("%llu %lld cpu_cores\n",   (unsigned long long)ts + 1, pp0_uj);
            // * it is given a vailue for 0 of 2uk, otherwise he have to chnage the provider logik.    
            if (domains & DOMAIN_GPU)
                printf("%llu %lld cpu_gpu\n", (unsigned long long)ts + 2, pp1_uj > 1 ? pp1_uj : 2);
            if ((domains & DOMAIN_DRAM)  && dram_uj >= 0)
                printf("%llu %lld dram\n",        (unsigned long long)ts + 3, dram_uj);
        }

        if (curr.valid) { prev = curr; first = 0; }

        /* Fixed sleep matching GMT's provider pattern */
        Sleep(interval_ms);
    }

    CloseHandle(hDev);
    return 0;
}
