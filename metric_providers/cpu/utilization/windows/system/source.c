/*
 * cpu_utilization_windows_system - source.c
 *
 * Reads system-wide CPU utilization via GetSystemTimes() and outputs it
 * in GMT format to stdout. Timing pattern (deadline-based loop, QPC clock)
 * mirrors metric_providers/cpu/energy/rapl/scaphandre/component.
 */

#include <windows.h>
#include <timeapi.h>    /* timeBeginPeriod / timeEndPeriod */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>

/* ---- CLI arg parsing (identical pattern to RAPL provider) ---- */
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

/* ---- Clock handling (identical pattern to RAPL provider) ---- */
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
    return (t - 116444736000000000ULL) / 10;  /* FILETIME epoch (1601) -> Unix epoch (1970), 100ns -> us */
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

/* ---- CPU time reading (this replaces read_cpu_proc() from procfs) ---- */
typedef struct {
    uint64_t idle;
    uint64_t kernel;   /* NOTE: kernel time INCLUDES idle time, same caveat as procfs system_time */
    uint64_t user;
} cpu_time_t;

static uint64_t filetime_to_u64(const FILETIME *ft)
{
    return ((uint64_t)ft->dwHighDateTime << 32) | ft->dwLowDateTime;
}

static void read_cpu_times(cpu_time_t *ct)
{
    FILETIME idle_ft, kernel_ft, user_ft;
    if (!GetSystemTimes(&idle_ft, &kernel_ft, &user_ft)) {
        fprintf(stderr, "Error - GetSystemTimes failed: %lu\n", GetLastError());
        exit(1);
    }
    ct->idle   = filetime_to_u64(&idle_ft);
    ct->kernel = filetime_to_u64(&kernel_ft);
    ct->user   = filetime_to_u64(&user_ft);
}

/* ---- main loop ---- */
int main(int argc, char **argv)
{
    unsigned int interval_ms = 1000;
    int c;
    int check_system_flag = 0;

    setvbuf(stdout, NULL, _IONBF, 0);

    for (c = 1; c < argc; c++) {
        if (strcmp(argv[c], "-h") == 0) {
            printf("Usage: %s [-i interval_ms] [-h] [-c]\n\n", argv[0]);
            printf("\t-h      : displays this help\n");
            printf("\t-i      : milliseconds between measurements\n");
            printf("\t-c      : check system and exit\n");
            return 0;
        } else if (strcmp(argv[c], "-i") == 0 && c + 1 < argc) {
            interval_ms = parse_int(argv[++c]);
        } else if (strcmp(argv[c], "-c") == 0) {
            check_system_flag = 1;
        }
    }

    if (check_system_flag) {
        FILETIME a, b, cc;
        if (!GetSystemTimes(&a, &b, &cc)) {
            fprintf(stderr, "GetSystemTimes not available\n");
            exit(1);
        }
        exit(0);
    }

    clock_state_t clock = clock_init();
    timeBeginPeriod(1);

    LARGE_INTEGER qpc_freq;
    QueryPerformanceFrequency(&qpc_freq);
    double qpc_ticks_per_ms = (double)qpc_freq.QuadPart / 1000.0;

    cpu_time_t prev;
    read_cpu_times(&prev);
    Sleep(interval_ms); /* wait one interval before the first snapshot so the first emitted value is meaningful, not a cold-start zero */

    while (1) {
        LONGLONG deadline = now_qpc() + (LONGLONG)(interval_ms * qpc_ticks_per_ms);

        cpu_time_t curr;
        read_cpu_times(&curr);

        /* same compute/non_compute split logic as procfs, mapped to Windows fields */
        uint64_t total_delta = (curr.user - prev.user) + (curr.kernel - prev.kernel);
        uint64_t idle_delta  = curr.idle - prev.idle;
        uint64_t busy_delta  = (total_delta > idle_delta) ? (total_delta - idle_delta) : 0;

        uint64_t ts_us = now_us(&clock);
        long value = (total_delta > 0) ? (long)((busy_delta * 10000ULL) / total_delta) : 0;

        printf("%llu %ld\n", (unsigned long long)ts_us, value);

        prev = curr;

        LONGLONG remaining_qpc = deadline - now_qpc();
        double sleep_ms = (remaining_qpc > 0) ? (remaining_qpc / qpc_ticks_per_ms) : 0.0;
        if (sleep_ms > 0) {
            Sleep((DWORD)sleep_ms);
        }
    }

    timeEndPeriod(1);
    return 0;
}
