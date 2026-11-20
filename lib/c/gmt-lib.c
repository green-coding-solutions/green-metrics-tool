#include "gmt-lib.h"

#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <limits.h>
#include <time.h>
#include <math.h>
#include <stdbool.h>
#include <sys/time.h>

bool is_partition_sysfs(unsigned int major_number, unsigned int minor_number) {
    char path[PATH_MAX];
    snprintf(path, sizeof(path), "/sys/dev/block/%u:%u/partition", major_number, minor_number);
    return access(path, F_OK) == 0;
}

int check_path(const char* path) {
    FILE* fd = fopen(path, "r");

    if (fd == NULL) {
        fprintf(stderr, "Couldn't open %s\n", path);
        exit(1);
    }
    fclose(fd);
    return 0;
}

unsigned int parse_int(char *argument) {
    unsigned int number = 0;
    char *endptr;

    errno = 0;  // Reset errno before the call
    number = strtoul(argument, &endptr, 10);

    if (errno == ERANGE && (number == UINT_MAX || number == 0)) {
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

    return number;
}

double parse_double(char *argument) {
    double number = 0.0;
    char *endptr;

    errno = 0;
    number = strtod(argument, &endptr);

    if (errno == ERANGE && (number == HUGE_VAL || number == -HUGE_VAL)) {
        fprintf(stderr, "Error: Could not parse float argument - out of range\n");
        exit(1);
    } else if (errno != 0 && number == 0.0) {
        fprintf(stderr, "Error: Could not parse float argument - invalid number\n");
        exit(1);
    } else if (endptr == argument) {
        fprintf(stderr, "Error: Could not parse float argument - no digits found\n");
        exit(1);
    } else if (*endptr != '\0') {
        fprintf(stderr, "Error: Could not parse float argument - invalid trailing characters\n");
        exit(1);
    }

    return number;
}

// Minimum allowed sampling interval, derived from the kernel's clock tick rate.
// /proc/stat counters are only updated once per tick (USER_HZ, typically 100Hz
// on Linux == 10ms per tick). Sampling faster than this can result in two reads
// landing within the same tick, producing a zero delta and a division by zero
// (SIGFPE) in providers that compute a ratio from consecutive /proc/stat reads.
unsigned int get_min_sleep_time_ms(void) {
    long ticks_per_sec = sysconf(_SC_CLK_TCK);
    if (ticks_per_sec <= 0) {
        fprintf(stderr, "Error - could not determine kernel clock tick rate via sysconf(_SC_CLK_TCK)\n");
        exit(1);
    }
    // ms per tick, rounded up so we never accept an interval that could
    // legitimately produce a zero-delta read
    return (unsigned int)((1000 + ticks_per_sec - 1) / ticks_per_sec);
}

// Rejects sampling intervals faster than the kernel updates /proc/stat.
// Otherwise two consecutive reads can land in the same tick, producing a
// zero total delta and a division-by-zero (SIGFPE) further down the line.
void validate_min_sleep_time(unsigned int msleep_time, unsigned int min_msleep_time_ms) {
    if (msleep_time < min_msleep_time_ms) {
        fprintf(stderr,
            "Error - requested sampling interval (%u ms) is below the kernel's "
            "clock tick period (%u ms). /proc/stat is only updated once per tick, "
            "so sampling faster than this can produce a zero-delta read and crash "
            "with a division by zero. Use -i %u or higher.\n",
            msleep_time, min_msleep_time_ms, min_msleep_time_ms);
        exit(1);
    }
}

// All metric providers timestamp with CLOCK_REALTIME, the same clock that Python's time.time() / time.time_ns()
// uses for phases and notes in the ScenarioRunner. GMT relies on both being in sync. Do not switch this to a
// monotonic clock + offset: CLOCK_MONOTONIC_RAW drifts away from CLOCK_REALTIME by the kernel's NTP frequency
// correction, and CLOCK_MONOTONIC / CLOCK_BOOTTIME diverge when the clock is set.
// If the clock is set backwards during a run, timestamps become non-monotonic and the run fails in
// BaseMetricProvider._check_monotonic() - which is wanted as the phase timestamps would be broken too.
void get_time(struct timeval *now) {
    struct timespec ts;
    if (clock_gettime(CLOCK_REALTIME, &ts) != 0) {
        perror("clock_gettime CLOCK_REALTIME");
        exit(EXIT_FAILURE);
    }

    now->tv_sec = ts.tv_sec;
    now->tv_usec = ts.tv_nsec / 1000; // microseconds precision
}
