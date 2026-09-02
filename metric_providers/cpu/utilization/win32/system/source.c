/*
 * cpu_utilization_win32_system - source.c
 *
 * Reads system-wide CPU utilization via GetSystemTimes() and outputs it
 * in GMT format to stdout. Fixed-interval sampling loop (Sleep(interval_ms)
 * between snapshots), consistent with the other GMT metric providers.
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

/* ---- CPU time reading (this replaces read_cpu_proc() from procfs) ----
 *
 * GetSystemTimes() is the only system-wide CPU time accounting the Win32 API
 * exposes and it reports exactly three counters - idle, kernel and user:
 * https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getsystemtimes
 *
 * Per that documentation the kernel counter "includes all threads in all
 * processes, in kernel mode" - and the idle thread runs in kernel mode, so
 * kernel time already contains idle time. Windows has no separate
 * "kernel-busy" counter the way /proc/stat separates system from idle on
 * Linux, so busy time has to be derived as (kernel + user) - idle. psutil's
 * Windows implementation applies the same correction.
 */
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

/* ---- Minimum sampling interval ----
 *
 * Windows accounts CPU time by charging each system clock interrupt to whatever
 * was running when it fired, so the idle/kernel/user counters only advance once
 * per clock tick. GetSystemTimeAdjustment() reports that tick period as
 * lpTimeIncrement in 100-nanosecond units:
 * https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemtimeadjustment
 *
 * Sampling faster than one tick means two consecutive reads can land inside the
 * same tick and produce a zero delta. Even where they do not, averaging a
 * sub-tick series maps a busy tick onto a shorter timeframe than it actually
 * occupied and averages the utilization away. Same reasoning and same guard as
 * on Linux, where lib/c/gmt-lib.c derives the floor from sysconf(_SC_CLK_TCK).
 *
 * Must be called after timeBeginPeriod(), because the increment reported here
 * follows the timer resolution the process has requested: ~15.6 ms by default,
 * ~1 ms once timeBeginPeriod(1) is in effect.
 */
static unsigned int get_min_sleep_time_ms(void)
{
    DWORD time_adjustment = 0;
    DWORD time_increment = 0;
    BOOL adjustment_disabled = FALSE;

    if (!GetSystemTimeAdjustment(&time_adjustment, &time_increment, &adjustment_disabled) || time_increment == 0) {
        fprintf(stderr, "Error - could not determine the system clock tick period via GetSystemTimeAdjustment: %lu\n", GetLastError());
        exit(1);
    }

    /* 100ns units -> ms, rounded up so we never accept an interval that could
       legitimately produce a zero-delta read */
    return (unsigned int)((time_increment + 9999) / 10000);
}

static void validate_min_sleep_time(unsigned int msleep_time, unsigned int min_msleep_time_ms)
{
    if (msleep_time < min_msleep_time_ms) {
        fprintf(stderr,
            "Error - requested sampling interval (%u ms) is below the system clock tick period (%u ms). "
            "The counters GetSystemTimes() reads only advance once per tick, so sampling faster than this "
            "produces zero-delta reads and averages utilization away. Use -i %u or higher.\n",
            msleep_time, min_msleep_time_ms, min_msleep_time_ms);
        exit(1);
    }
}

/* ---- main loop ---- */
int main(int argc, char **argv)
{
    unsigned int interval_ms = 1000;
    unsigned int min_msleep_time_ms;
    int c;
    int check_system_flag = 0;

    setvbuf(stdout, NULL, _IONBF, 0);

    /* before reading the tick period, so the floor reflects the resolution this
       process actually samples at rather than the system default */
    timeBeginPeriod(1);
    min_msleep_time_ms = get_min_sleep_time_ms();

    for (c = 1; c < argc; c++) {
        if (strcmp(argv[c], "-h") == 0) {
            printf("Usage: %s [-i interval_ms] [-h] [-c]\n\n", argv[0]);
            printf("\t-h      : displays this help\n");
            printf("\t-i      : milliseconds between measurements\n");
            printf("\t          (must be >= the system clock tick period, currently %u ms)\n", min_msleep_time_ms);
            printf("\t-c      : check system and exit\n");
            printf("\n");
            printf("\tSystemTickMS\t%u\n", min_msleep_time_ms);
            timeEndPeriod(1);
            return 0;
        } else if (strcmp(argv[c], "-i") == 0 && c + 1 < argc) {
            interval_ms = parse_int(argv[++c]);
        } else if (strcmp(argv[c], "-c") == 0) {
            check_system_flag = 1;
        }
    }

    if (check_system_flag) {
        FILETIME a, b, cc;
        DWORD cpu_count;

        if (!GetSystemTimes(&a, &b, &cc)) {
            fprintf(stderr, "GetSystemTimes not available\n");
            exit(1);
        }

        /* GetSystemTimes() only ever reports the times of the processor group the
           calling thread runs in, so on machines with more than 64 logical
           processors - which Windows splits into multiple processor groups - it
           silently measures a subset of the machine:
           https://learn.microsoft.com/en-us/windows/win32/procthread/processor-groups */
        cpu_count = GetActiveProcessorCount(ALL_PROCESSOR_GROUPS);
        if (cpu_count > 64) {
            fprintf(stderr,
                "Error - system has %lu logical processors across all processor groups. "
                "GetSystemTimes() only covers a single group, so it cannot measure this machine. "
                "Use cpu_utilization_ntapi_core instead.\n", (unsigned long)cpu_count);
            exit(1);
        }

        timeEndPeriod(1);
        exit(0);
    }

    validate_min_sleep_time(interval_ms, min_msleep_time_ms);

    clock_state_t clock = clock_init();

    cpu_time_t prev, curr;
    read_cpu_times(&prev);
    Sleep(interval_ms); /* wait one interval before the first snapshot so the first emitted value is meaningful, not a cold-start zero */

    while (1) {
        read_cpu_times(&curr);

        /* Windows' KernelTime already includes IdleTime (unlike Linux's separate
         * idle/system counters), so kernel_delta below still contains the idle
         * portion. total_delta is therefore "kernel (incl. idle) + user", and we
         * subtract idle_delta to arrive at the actual busy time. */
        uint64_t kernel_delta = curr.kernel - prev.kernel;
        uint64_t user_delta   = curr.user   - prev.user;
        uint64_t idle_delta   = curr.idle   - prev.idle;

        uint64_t total_delta = kernel_delta + user_delta;
        uint64_t busy_delta  = (total_delta > idle_delta) ? (total_delta - idle_delta) : 0;

        uint64_t ts_us = now_us(&clock);
        /* Deliberate integer conversion. Precision with 0.01% is good enough - same as procfs provider */
        long value = (total_delta > 0) ? (long)((busy_delta * 10000ULL) / total_delta) : 0;

        printf("%llu %ld\n", (unsigned long long)ts_us, value);

        prev = curr;

        Sleep(interval_ms);
    }

    timeEndPeriod(1);
    return 0;
}
