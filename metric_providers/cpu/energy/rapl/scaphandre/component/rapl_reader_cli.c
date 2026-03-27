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
 * Unit: uJ (micro-Joules) to avoid GMT resolution underflow
 *
 * Usage:
 *   rapl_reader.exe -i <interval_ms>
 *   rapl_reader.exe -c              (check mode)
 *
 * Build (x64 Native Tools Command Prompt for VS 2022):
 *   cl rapl_reader_cli.c /Fe:rapl_reader.exe /O2 /W3
 */

#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

#pragma pack(push, 1)
typedef struct { uint32_t msrRegister; uint32_t cpuIndex; } msr_request_t;
#pragma pack(pop)

typedef struct {
    double pkg_energy_j, dram_energy_j, pp0_energy_j, pp1_energy_j;
    double energy_unit;
    int valid;
} rapl_sample_t;

static HANDLE open_driver(void) {
    return CreateFileA(DEVICE_PATH, GENERIC_READ|GENERIC_WRITE, 0, NULL,
                       OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
}

static int read_msr(HANDLE hDev, uint32_t reg, uint32_t cpu, uint64_t *out) {
    msr_request_t req = {reg, cpu};
    DWORD bytes = 0;
    BOOL ok = DeviceIoControl(hDev, IOCTL_READ_MSR, &req, sizeof(req),
                               out, sizeof(*out), &bytes, NULL);
    return (ok && bytes >= sizeof(uint64_t)) ? 0 : -1;
}

static rapl_sample_t read_rapl(HANDLE hDev, uint32_t cpu) {
    rapl_sample_t s = {0};
    uint64_t raw = 0;
    if (read_msr(hDev, MSR_RAPL_POWER_UNIT, cpu, &raw) != 0)
        if (read_msr(hDev, MSR_AMD_RAPL_POWER_UNIT, cpu, &raw) != 0) return s;
    s.energy_unit = 1.0 / (double)(1ULL << ((raw >> 8) & 0x1F));
    if (read_msr(hDev, MSR_PKG_ENERGY_STATUS,  cpu, &raw) == 0) s.pkg_energy_j  = (raw & 0xFFFFFFFF) * s.energy_unit;
    if (read_msr(hDev, MSR_DRAM_ENERGY_STATUS, cpu, &raw) == 0) s.dram_energy_j = (raw & 0xFFFFFFFF) * s.energy_unit;
    if (read_msr(hDev, MSR_PP0_ENERGY_STATUS,  cpu, &raw) == 0) s.pp0_energy_j  = (raw & 0xFFFFFFFF) * s.energy_unit;
    if (read_msr(hDev, MSR_PP1_ENERGY_STATUS,  cpu, &raw) == 0) s.pp1_energy_j  = (raw & 0xFFFFFFFF) * s.energy_unit;
    s.valid = 1;
    return s;
}

static uint64_t now_us(void) {
    FILETIME ft; GetSystemTimeAsFileTime(&ft);
    uint64_t t = ((uint64_t)ft.dwHighDateTime << 32) | ft.dwLowDateTime;
    return (t - 116444736000000000ULL) / 10;
}

static long long delta_uj(double curr, double prev, double eu) {
    double d = curr - prev;
    if (d < 0) d += (double)(1ULL << 32) * eu;
    return (long long)(d * 1000000.0);
}

int main(int argc, char *argv[]) {
    int interval_ms = 100, check_mode = 0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-i") && i+1 < argc) interval_ms = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-c")) check_mode = 1;
    }

    HANDLE hDev = open_driver();
    if (hDev == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "Cannot open driver. Error: %lu\n", GetLastError());
        return 1;
    }

    if (check_mode) {
        uint64_t raw = 0;
        int ok = read_msr(hDev, MSR_RAPL_POWER_UNIT, 0, &raw);
        CloseHandle(hDev);
        return (ok == 0) ? 0 : 1;
    }

    setvbuf(stdout, NULL, _IONBF, 0);
    rapl_sample_t prev = {0};
    int first = 1;

    while (1) {
        DWORD t_start = GetTickCount();
        rapl_sample_t curr = read_rapl(hDev, 0);
        uint64_t ts = now_us();

        if (curr.valid && !first) {
            long long pkg_uj  = delta_uj(curr.pkg_energy_j,  prev.pkg_energy_j,  curr.energy_unit);
            long long pp0_uj  = delta_uj(curr.pp0_energy_j,  prev.pp0_energy_j,  curr.energy_unit);
            long long pp1_uj  = delta_uj(curr.pp1_energy_j,  prev.pp1_energy_j,  curr.energy_unit);
            long long dram_uj = delta_uj(curr.dram_energy_j, prev.dram_energy_j, curr.energy_unit);

            /* Skip values <= 1 to avoid GMT resolution underflow and dont use same timestamp */              /* cpu_gpu immer ausgeben, auch kleine Werte */
            if (pkg_uj  > 1) printf("%llu %lld cpu_package\n", (unsigned long long)ts,     pkg_uj);
            if (pp0_uj  > 1) printf("%llu %lld cpu_cores\n",   (unsigned long long)ts + 1, pp0_uj);
            printf("%llu %lld cpu_gpu\n", (unsigned long long)ts + 2, pp1_uj > 0 ? pp1_uj : 2);
            if (dram_uj > 1) printf("%llu %lld dram\n",        (unsigned long long)ts + 3, dram_uj);
        }

        if (curr.valid) { prev = curr; first = 0; }

        DWORD elapsed = GetTickCount() - t_start;
        if ((DWORD)interval_ms > elapsed) Sleep(interval_ms - elapsed);
    }

    CloseHandle(hDev);
    return 0;
}