#include "gmt-lib.h"

#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <limits.h>
#include <time.h>
#include <sys/time.h>

bool is_partition_sysfs(const char *devname) {
    char path[PATH_MAX];
    snprintf(path, sizeof(path), "/sys/class/block/%s/partition", devname);
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

void get_time_offset(struct timespec *offset) {
    struct timespec realtime, monotonic;

    if (clock_gettime(CLOCK_REALTIME, &realtime) != 0) {
        perror("clock_gettime CLOCK_REALTIME");
        exit(EXIT_FAILURE);
    }
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &monotonic) != 0) {
        perror("clock_gettime CLOCK_MONOTONIC_RAW");
        exit(EXIT_FAILURE);
    }
    offset->tv_sec = realtime.tv_sec - monotonic.tv_sec;
    offset->tv_nsec = realtime.tv_nsec - monotonic.tv_nsec;
    if (offset->tv_nsec < 0) {
        offset->tv_sec -= 1;
        offset->tv_nsec += 1000000000L;
    }
}

void get_adjusted_time(struct timeval *adjusted, struct timespec *offset) {
    struct timespec now_monotonic;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &now_monotonic) != 0) {
        perror("clock_gettime CLOCK_MONOTONIC_RAW");
        exit(EXIT_FAILURE);
    }

    // Convert to microseconds precision
    adjusted->tv_sec = now_monotonic.tv_sec + offset->tv_sec;
    adjusted->tv_usec = (now_monotonic.tv_nsec / 1000) + (offset->tv_nsec / 1000);

    if (adjusted->tv_usec >= 1000000) {
        adjusted->tv_sec += adjusted->tv_usec / 1000000;
        adjusted->tv_usec %= 1000000;
    }
}
