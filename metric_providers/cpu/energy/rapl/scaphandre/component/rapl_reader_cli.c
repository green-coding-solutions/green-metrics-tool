/*
 * rapl_reader_cli.c
 *
 * Windows CLI tool that reads RAPL MSR values directly from the
 * ScaphandreDrv kernel driver and outputs them in GMT format to stdout.
 *
 * Output format (GMT standard):
 *   timestamp_microseconds value detail_name
 *   1774007770584099 3614000 cpu_package
 *
 * Unit: uJ (micro-Joules), consistent with CpuEnergyRaplMsrComponentProvider.
 *
 * Timing: QueryPerformanceCounter (monotonic, ~100ns resolution)
 * + wall-clock offset at startup. Immune to DST and leap seconds.
 * Mirrors GMT's gmt-lib.c get_time_offset() / get_adjusted_time().
 * Each domain gets its own timestamp via now_us() to ensure unique
 * timestamps without artificial offsets.
 *
 * Usage:
 *   rapl_reader.exe -i <interval_ms>        (default: 99ms)
 *   rapl_reader.exe -i 99 -d cpu_package    (single domain)
 *   rapl_reader.exe -c                      (check mode)
 *
 * Available domains: cpu_package, cpu_cores, cpu_gpu, dram, psys
 * Default: all supported domains (auto-detected at startup)
 *
 * Exit codes:
 *   0 = clean exit (check mode success)
 *   1 = startup error (driver not found, bad args)
 *   2 = runtime error (driver disappeared during measurement)
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

#define DEVICE_PATH "\\\\.\\ScaphandreDriver"
#define IOCTL_READ_MSR CTL_CODE(FILE_DEVICE_UNKNOWN, 0x800, METHOD_BUFFERED, FILE_ANY_ACCESS)

#define MSR_RAPL_POWER_UNIT        0x00000606
#define MSR_PKG_ENERGY_STATUS      0x00000611
#define MSR_DRAM_ENERGY_STATUS     0x00000619
#define MSR_PP0_ENERGY_STATUS      0x00000639
#define MSR_PP1_ENERGY_STATUS      0x00000641
#define MSR_PLATFORM_ENERGY_STATUS 0x0000064d
#define MSR_AMD_RAPL_POWER_UNIT    0xc0010299
#define MSR_AMD_PKG_ENERGY_STATUS  0xc001029b
#define MSR_AMD_CORE_ENERGY_STATUS 0xc001029a

#define DOMAIN_PKG   (1 << 0)
#define DOMAIN_CORES (1 << 1)
#define DOMAIN_GPU   (1 << 2)
#define DOMAIN_DRAM  (1 << 3)
#define DOMAIN_PSYS  (1 << 4)
#define DOMAIN_ALL   (DOMAIN_PKG | DOMAIN_CORES | DOMAIN_GPU | DOMAIN_DRAM | DOMAIN_PSYS)

/*
 * MAX_CONSECUTIVE_ERRORS: how many failed read_msr() calls in a row
 * before we treat the driver as gone and exit with code 2.
 * At 99ms interval: 5 errors = ~500ms grace period before giving up.
 * This lets GMT detect the process died and report it, rather than
 * silently getting no data for the rest of the test.
 */
#define MAX_CONSECUTIVE_ERRORS 5

#pragma pack(push, 1)
typedef struct { uint32_t msrRegister; uint32_t cpuIndex; } msr_request_t;
#pragma pack(pop)

typedef struct {
    double pkg_energy_j;
    double dram_energy_j;
    double pp0_energy_j;
    double pp1_energy_j;
    double psys_energy_j;
    int    valid;      /* 0 if ANY domain read failed (driver error) */
    int    ioctl_err;  /* 1 if the failure was an IOCTL error specifically */
} rapl_sample_t;

typedef struct {
    LARGE_INTEGER qpc_start;
    uint64_t      wall_start_us;
    double        qpc_freq_us;
} clock_state_t;

static unsigned int parse_int(char *argument)
{
    unsigned long number = 0;
    char *endptr;
    errno = 0;
    number = strtoul(argument, &endptr, 10);
    if (errno == ERANGE && (number == ULONG_MAX || number == 0)) {
        fprintf(stderr, "Error: Could not parse -i argument - Number out of range\n"); exit(1);
    } else if (errno != 0 && number == 0) {
        fprintf(stderr, "Error: Could not parse -i argument - Invalid number\n"); exit(1);
    } else if (endptr == argument) {
        fprintf(stderr, "Error: Could not parse -i argument - No digits were found\n"); exit(1);
    } else if (*endptr != '\0') {
        fprintf(stderr, "Error: Could not parse -i argument - Invalid characters after number\n"); exit(1);
    }
    return (unsigned int)number;
}

static uint64_t get_wall_time_us(void)
{
    FILETIME ft;
    GetSystemTimeAsFileTime(&ft);
    uint64_t t = ((uint64_t)ft.dwHighDateTime << 32) | ft.dwLowDateTime;
    return (t - 116444736000000000ULL) / 10;
}

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

static uint64_t now_us(const clock_state_t *cs)
{
    LARGE_INTEGER qpc_now;
    QueryPerformanceCounter(&qpc_now);
    double elapsed_us = (double)(qpc_now.QuadPart - cs->qpc_start.QuadPart) / cs->qpc_freq_us;
    return cs->wall_start_us + (uint64_t)elapsed_us;
}

static HANDLE open_driver(void)
{
    return CreateFileA(DEVICE_PATH, GENERIC_READ | GENERIC_WRITE, 0, NULL,
                       OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
}

static int read_msr(HANDLE hDev, uint32_t reg, uint32_t cpu, uint64_t *out)
{
    msr_request_t req = { reg, cpu };
    DWORD bytes = 0;
    BOOL ok = DeviceIoControl(hDev, IOCTL_READ_MSR, &req, sizeof(req),
                               out, sizeof(*out), &bytes, NULL);
    return (ok && bytes >= sizeof(uint64_t)) ? 0 : -1;
}

static double read_energy_unit(HANDLE hDev, uint32_t cpu)
{
    uint64_t raw = 0;
    if (read_msr(hDev, MSR_RAPL_POWER_UNIT, cpu, &raw) != 0)
        if (read_msr(hDev, MSR_AMD_RAPL_POWER_UNIT, cpu, &raw) != 0)
            return -1.0;
    return 1.0 / (double)(1ULL << ((raw >> 8) & 0x1F));
}

/*
 * is_domain_active() - auto-detect if a RAPL domain is active.
 * Takes N samples at interval_ms apart. Returns 0 if ALL samples
 * are <= 1 uJ (domain inactive), 1 otherwise.
 * Runs within GMT's 2-second startup delay.
 */
static int is_domain_active(HANDLE hDev, uint32_t cpu,
                             uint32_t msr_reg, double energy_unit,
                             int samples, int interval_ms)
{
    uint64_t prev = 0, curr = 0;
    int zero_count = 0;

    if (read_msr(hDev, msr_reg, cpu, &prev) != 0) return 0;

    for (int i = 0; i < samples; i++) {
        Sleep(interval_ms);
        if (read_msr(hDev, msr_reg, cpu, &curr) != 0) return 0;
        double delta = ((double)(curr & 0xFFFFFFFF) - (double)(prev & 0xFFFFFFFF)) * energy_unit;
        if (delta < 0) delta += (double)(1ULL << 32) * energy_unit;
        if ((long long)(delta * 1000000.0) <= 1) zero_count++;
        prev = curr;
    }
    return (zero_count < samples) ? 1 : 0;
}

/*
 * read_rapl() - read all enabled RAPL domains.
 *
 * Returns a sample with valid=1 on success.
 * Returns valid=0, ioctl_err=1 if the PKG domain read fails –
 * PKG is always enabled and is the canary for driver health.
 * Other domain failures are non-fatal (domain stays at 0).
 */
static rapl_sample_t read_rapl(HANDLE hDev, uint32_t cpu,
                                double energy_unit, int domains)
{
    rapl_sample_t s = {0};
    uint64_t raw = 0;

    /* PKG is our canary: if this fails the driver is gone */
    if (domains & DOMAIN_PKG) {
        if (read_msr(hDev, MSR_PKG_ENERGY_STATUS, cpu, &raw) != 0) {
            s.valid     = 0;
            s.ioctl_err = 1;
            return s;
        }
        s.pkg_energy_j = (raw & 0xFFFFFFFF) * energy_unit;
    }

    if (domains & DOMAIN_DRAM)
        if (read_msr(hDev, MSR_DRAM_ENERGY_STATUS, cpu, &raw) == 0)
            s.dram_energy_j = (raw & 0xFFFFFFFF) * energy_unit;
    if (domains & DOMAIN_CORES)
        if (read_msr(hDev, MSR_PP0_ENERGY_STATUS, cpu, &raw) == 0)
            s.pp0_energy_j = (raw & 0xFFFFFFFF) * energy_unit;
    if (domains & DOMAIN_GPU)
        if (read_msr(hDev, MSR_PP1_ENERGY_STATUS, cpu, &raw) == 0)
            s.pp1_energy_j = (raw & 0xFFFFFFFF) * energy_unit;
    if (domains & DOMAIN_PSYS)
        if (read_msr(hDev, MSR_PLATFORM_ENERGY_STATUS, cpu, &raw) == 0)
            s.psys_energy_j = (raw & 0xFFFFFFFF) * energy_unit;

    s.valid = 1;
    return s;
}

static long long delta_uj(double curr, double prev, double eu)
{
    double d = curr - prev;
    if (d < 0) d += (double)(1ULL << 32) * eu;
    return (long long)(d * 1000000.0);
}

static int parse_domain(const char *d)
{
    if (!strcmp(d, "cpu_package")) return DOMAIN_PKG;
    if (!strcmp(d, "cpu_cores"))   return DOMAIN_CORES;
    if (!strcmp(d, "cpu_gpu"))     return DOMAIN_GPU;
    if (!strcmp(d, "dram"))        return DOMAIN_DRAM;
    if (!strcmp(d, "psys"))        return DOMAIN_PSYS;
    fprintf(stderr, "Error: Unknown domain '%s'. Valid: cpu_package, cpu_cores, cpu_gpu, dram, psys\n", d);
    exit(1);
}

int main(int argc, char *argv[])
{
    unsigned int interval_ms  = 99;
    int check_mode            = 0;
    int domains               = DOMAIN_ALL;
    int user_domains          = 0; /* 1 if -d was used (single domain mode) */
    int excluded_domains      = 0; /* domains explicitly disabled via -x */

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-i") && i + 1 < argc)
            interval_ms = parse_int(argv[++i]);
        else if (!strcmp(argv[i], "-d") && i + 1 < argc) {
            /* Set a single domain explicitly - skips auto-detection */
            domains      = parse_domain(argv[++i]);
            user_domains = 1;
        }
        else if (!strcmp(argv[i], "-x") && i + 1 < argc) {
            /* Comma-separated list of domains to disable e.g. -x cpu_gpu,dram */
            char buf[256];
            strncpy(buf, argv[++i], sizeof(buf) - 1);
            buf[sizeof(buf) - 1] = '\0';
            char *token = strtok(buf, ",");
            while (token) {
                excluded_domains |= parse_domain(token);
                token = strtok(NULL, ",");
            }
        }
        else if (!strcmp(argv[i], "-c"))
            check_mode = 1;
    }

    HANDLE hDev = open_driver();
    if (hDev == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "Cannot open driver. Error: %lu\n", GetLastError());
        return 1;
    }

    if (check_mode) {
        double eu = read_energy_unit(hDev, 0);
        CloseHandle(hDev);
        return (eu > 0) ? 0 : 1;
    }

    double energy_unit = read_energy_unit(hDev, 0);
    if (energy_unit <= 0) {
        fprintf(stderr, "Cannot read RAPL power unit MSR.\n");
        CloseHandle(hDev);
        return 1;
    }

    /* Apply explicit exclusions BEFORE auto-detection so excluded
     * domains are never checked and never measured */
    domains &= ~excluded_domains;

    /*
     * PKG domain is our IOCTL canary in read_rapl().
     * If the user excluded PKG explicitly with -x, we need a fallback
     * canary or we can't detect driver loss. In that edge case we keep
     * PKG active internally (read only, not printed).
     * Flag this so the output section knows not to print PKG.
     */
    int pkg_excluded = (excluded_domains & DOMAIN_PKG) ? 1 : 0;
    if (pkg_excluded)
        domains |= DOMAIN_PKG; /* re-add as silent canary */

    setvbuf(stdout, NULL, _IONBF, 0);
    clock_state_t cs = clock_init();

    /*
     * Auto-detect active domains at startup (5 samples x 100ms each).
     * Only runs for domains that are still active after -x exclusions.
     * Skipped entirely if user set a single domain via -d.
     * Runs within GMT's 2-second startup delay.
     */
    if (!user_domains) {
        if ((domains & DOMAIN_DRAM) &&
            !is_domain_active(hDev, 0, MSR_DRAM_ENERGY_STATUS, energy_unit, 5, 100)) {
            domains &= ~DOMAIN_DRAM;
            fprintf(stderr, "Info: DRAM domain not supported on this CPU, disabling.\n");
        }
        if ((domains & DOMAIN_GPU) &&
            !is_domain_active(hDev, 0, MSR_PP1_ENERGY_STATUS, energy_unit, 5, 100)) {
            domains &= ~DOMAIN_GPU;
            fprintf(stderr, "Info: GPU domain not supported on this CPU, disabling.\n");
        }
        if ((domains & DOMAIN_PSYS) &&
            !is_domain_active(hDev, 0, MSR_PLATFORM_ENERGY_STATUS, energy_unit, 5, 100)) {
            domains &= ~DOMAIN_PSYS;
            fprintf(stderr, "Info: PSYS domain not supported on this CPU, disabling.\n");
        }
    }

    rapl_sample_t prev     = {0};
    int first              = 1;
    int consecutive_errors = 0;  /* counts back-to-back IOCTL failures */

    while (1) {
        rapl_sample_t curr = read_rapl(hDev, 0, energy_unit, domains);

        if (!curr.valid && curr.ioctl_err) {
            /*
             * Driver read failed. Count consecutive errors.
             * A single transient failure (e.g. brief driver hiccup) is
             * tolerated. After MAX_CONSECUTIVE_ERRORS we give up cleanly
             * so GMT can detect the process is gone and log the gap.
             */
            consecutive_errors++;
            fprintf(stderr,
                "Warning: IOCTL read failed (error %lu), attempt %d/%d\n",
                GetLastError(), consecutive_errors, MAX_CONSECUTIVE_ERRORS);

            if (consecutive_errors >= MAX_CONSECUTIVE_ERRORS) {
                fprintf(stderr,
                    "Fatal: ScaphandreDrv driver lost after %d consecutive "
                    "failures. Is the driver still running?\n"
                    "  Check: sc.exe query ScaphandreDrv\n"
                    "  Start: sc.exe start ScaphandreDrv\n",
                    MAX_CONSECUTIVE_ERRORS);
                CloseHandle(hDev);
                return 2;  /* exit code 2 = runtime driver loss */
            }

            Sleep(interval_ms);
            continue;
        }

        /* Successful read: reset error counter */
        consecutive_errors = 0;

        if (curr.valid && !first) {
            long long pkg_uj  = delta_uj(curr.pkg_energy_j,  prev.pkg_energy_j,  energy_unit);
            long long pp0_uj  = delta_uj(curr.pp0_energy_j,  prev.pp0_energy_j,  energy_unit);
            long long pp1_uj  = delta_uj(curr.pp1_energy_j,  prev.pp1_energy_j,  energy_unit);
            long long dram_uj = delta_uj(curr.dram_energy_j, prev.dram_energy_j, energy_unit);
            long long psys_uj = delta_uj(curr.psys_energy_j, prev.psys_energy_j, energy_unit);

            /*
             * Each domain calls now_us() individually so timestamps are
             * naturally unique (QPC ~100ns resolution) without artificial offsets.
             *
             * Only negative values are skipped (overflow edge cases),
             * matching GMT's native RAPL provider (source.c line 478).
             *
             * GPU uses a minimum fallback of 2 uJ when value is 0 to prevent
             * GMT resolution underflow while keeping the time series gap-free.
             * See PR discussion for cleaner alternatives.
             *
             * PKG is skipped from output if the user excluded it via -x
             * (it still runs internally as the IOCTL canary).
             */
            if ((domains & DOMAIN_PKG)   && !pkg_excluded && pkg_uj  >= 0)
                printf("%llu %lld cpu_package\n", (unsigned long long)now_us(&cs), pkg_uj);
            if ((domains & DOMAIN_CORES) && pp0_uj  >= 0)
                printf("%llu %lld cpu_cores\n",   (unsigned long long)now_us(&cs), pp0_uj);
            if  (domains & DOMAIN_GPU)
                printf("%llu %lld cpu_gpu\n",     (unsigned long long)now_us(&cs), pp1_uj > 1 ? pp1_uj : 2);
            if ((domains & DOMAIN_DRAM)  && dram_uj >= 0)
                printf("%llu %lld dram\n",        (unsigned long long)now_us(&cs), dram_uj);
            if ((domains & DOMAIN_PSYS)  && psys_uj >= 0)
                printf("%llu %lld psys\n",        (unsigned long long)now_us(&cs), psys_uj);
        }

        if (curr.valid) { prev = curr; first = 0; }

        Sleep(interval_ms);
    }

    CloseHandle(hDev);
    return 0;
}
