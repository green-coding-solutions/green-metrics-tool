/*
 * cpu_utilization_windows_core - source.c
 *
 * Per-core CPU utilization on Windows via NtQuerySystemInformation
 * (SystemProcessorPerformanceInformation). Outputs busy%, and optionally
 * interrupt%/DPC% per logical core, in GMT's TIMESTAMP VALUE DETAIL_NAME
 * format.
 *
 * NtQuerySystemInformation is an undocumented NT API; the struct layout
 * used here is the publicly known, ABI-stable layout (unchanged since
 * Windows XP, confirmed via ReactOS/Sysinternals-adjacent sources and
 * matching psutil's own Windows implementation). If the layout were
 * ever wrong, the call fails cleanly with STATUS_INFO_LENGTH_MISMATCH
 * rather than silently returning corrupt data.
 */

#include <windows.h>
#include <timeapi.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
/* ---- NtQuerySystemInformation: undocumented, loaded dynamically ---- */
typedef LONG NTSTATUS;
#define STATUS_SUCCESS 0x00000000L
#define SystemProcessorPerformanceInformationClass 8

typedef struct _SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION {
    LARGE_INTEGER IdleTime;
    LARGE_INTEGER KernelTime;
    LARGE_INTEGER UserTime;
    LARGE_INTEGER DpcTime;
    LARGE_INTEGER InterruptTime;
    ULONG InterruptCount;
} SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION;

typedef NTSTATUS (WINAPI *NtQuerySystemInformation_t)(
    ULONG SystemInformationClass,
    PVOID SystemInformation,
    ULONG SystemInformationLength,
    PULONG ReturnLength
);

static NtQuerySystemInformation_t NtQuerySystemInformation_fn = NULL;

static void load_ntdll_functions(void) {
    HMODULE ntdll = GetModuleHandleA("ntdll.dll");
    if (ntdll == NULL) {
        fprintf(stderr, "Error - could not get handle to ntdll.dll\n");
        exit(1);
    }
    NtQuerySystemInformation_fn = (NtQuerySystemInformation_t)GetProcAddress(ntdll, "NtQuerySystemInformation");
    if (NtQuerySystemInformation_fn == NULL) {
        fprintf(stderr, "Error - could not resolve NtQuerySystemInformation\n");
        exit(1);
    }
}

/* ---- CLI arg parsing (unchanged pattern) ---- */
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

/* ---- Clock handling (identical to system provider) ---- */
typedef struct {
    LARGE_INTEGER qpc_start;
    uint64_t      wall_start_us;
    double        qpc_freq_us;
} clock_state_t;

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

static LONGLONG now_qpc(void)
{
    LARGE_INTEGER qpc;
    QueryPerformanceCounter(&qpc);
    return qpc.QuadPart;
}

/* ---- Per-core snapshot reading ---- */
static unsigned int get_ncpus(void)
{
    unsigned int ncpus = GetActiveProcessorCount(ALL_PROCESSOR_GROUPS);
    if (ncpus == 0) {
        fprintf(stderr, "Error - GetActiveProcessorCount returned 0\n");
        exit(1);
    }
    return ncpus;
}

static void read_per_core_times(SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION *buf, unsigned int ncpus)
{
    ULONG buffer_size = ncpus * sizeof(SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION);
    ULONG return_length = 0;

    NTSTATUS status = NtQuerySystemInformation_fn(
        SystemProcessorPerformanceInformationClass,
        buf,
        buffer_size,
        &return_length
    );

    if (status != STATUS_SUCCESS) {
        fprintf(stderr, "Error - NtQuerySystemInformation failed with status 0x%lX "
                        "(expected buffer %lu bytes, got %lu bytes back). "
                        "This likely means the SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION "
                        "struct layout does not match this Windows version.\n",
                (unsigned long)status, buffer_size, return_length);
        exit(1);
    }
}

/* ---- main loop ---- */
int main(int argc, char **argv)
{
    unsigned int interval_ms = 1000;
    int c;
    int check_system_flag = 0;
    int include_interrupt_dpc = 0; /* lean default: off */
    unsigned int ncpus;
    unsigned int i;

    setvbuf(stdout, NULL, _IONBF, 0);

    for (c = 1; c < argc; c++) {
        if (strcmp(argv[c], "-h") == 0) {
            printf("Usage: %s [-i interval_ms] [-h] [-c] [--with-interrupt-dpc]\n\n", argv[0]);
            printf("\t-h      : displays this help\n");
            printf("\t-i      : milliseconds between measurements\n");
            printf("\t-c      : check system and exit\n");
            printf("\t--with-interrupt-dpc : also output per-core interrupt/DPC time (off by default)\n");
            return 0;
        } else if (strcmp(argv[c], "-i") == 0 && c + 1 < argc) {
            interval_ms = parse_int(argv[++c]);
        } else if (strcmp(argv[c], "-c") == 0) {
            check_system_flag = 1;
        } else if (strcmp(argv[c], "--with-interrupt-dpc") == 0) {
            include_interrupt_dpc = 1;
        }
    }

    load_ntdll_functions();
    ncpus = get_ncpus();

    if (check_system_flag) {
        SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION *test_buf =
            malloc(ncpus * sizeof(SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION));
        if (test_buf == NULL) {
            fprintf(stderr, "Error - could not allocate check buffer\n");
            exit(1);
        }
        read_per_core_times(test_buf, ncpus);
        free(test_buf);
        exit(0);
    }

    clock_state_t clock = clock_init();
    timeBeginPeriod(1);

    LARGE_INTEGER qpc_freq;
    QueryPerformanceFrequency(&qpc_freq);
    double qpc_ticks_per_ms = (double)qpc_freq.QuadPart / 1000.0;

    SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION *prev =
        malloc(ncpus * sizeof(SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION));
    SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION *curr =
        malloc(ncpus * sizeof(SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION));
    if (prev == NULL || curr == NULL) {
        fprintf(stderr, "Error - could not allocate per-core buffers\n");
        exit(1);
    }

    read_per_core_times(prev, ncpus);
    Sleep(interval_ms); /* wait one interval before the loop starts so the first emitted value already reflects a real interval, not a cold-start zero */

    while (1) {
        LONGLONG deadline = now_qpc() + (LONGLONG)(interval_ms * qpc_ticks_per_ms);

        read_per_core_times(curr, ncpus);
        uint64_t ts_us = now_us(&clock);

        for (i = 0; i < ncpus; i++) {
            uint64_t idle_d   = curr[i].IdleTime.QuadPart      - prev[i].IdleTime.QuadPart;
            uint64_t kernel_d = curr[i].KernelTime.QuadPart    - prev[i].KernelTime.QuadPart;
            uint64_t user_d   = curr[i].UserTime.QuadPart      - prev[i].UserTime.QuadPart;
            uint64_t dpc_d    = curr[i].DpcTime.QuadPart       - prev[i].DpcTime.QuadPart;
            uint64_t intr_d   = curr[i].InterruptTime.QuadPart - prev[i].InterruptTime.QuadPart;

            uint64_t busy_d  = (user_d + kernel_d) - idle_d; /* kernel includes idle, same as system provider */
            uint64_t total_d = user_d + kernel_d;

            long busy_value = (total_d > 0) ? (long)((busy_d  * 10000ULL) / total_d) : 0;

            printf("%llu %ld core_%u\n", (unsigned long long)ts_us, busy_value, i);

            if (include_interrupt_dpc) {
                long dpc_value  = (total_d > 0) ? (long)((dpc_d  * 10000ULL) / total_d) : 0;
                long intr_value = (total_d > 0) ? (long)((intr_d * 10000ULL) / total_d) : 0;

                printf("%llu %ld core_%u_dpc\n",       (unsigned long long)ts_us, dpc_value,  i);
                printf("%llu %ld core_%u_interrupt\n", (unsigned long long)ts_us, intr_value, i);
            }
        }

        SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION *tmp = prev;
        prev = curr;
        curr = tmp;

        LONGLONG remaining_qpc = deadline - now_qpc();
        double sleep_ms = (remaining_qpc > 0) ? (remaining_qpc / qpc_ticks_per_ms) : 0.0;
        if (sleep_ms > 0) {
            Sleep((DWORD)sleep_ms);
        }
    }

    timeEndPeriod(1);
    free(prev);
    free(curr);
    return 0;
}
