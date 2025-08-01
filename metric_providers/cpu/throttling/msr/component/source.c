#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <errno.h>
#include <inttypes.h>
#include <unistd.h>
#include <math.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/time.h>
#include <time.h>
#include <limits.h>
#include <stdbool.h>
#include "gmt-lib.h"

#define IA32_THERM_STATUS 0x19C
#define THERMAL_THROTTLING_STATUS_BIT (1 << 0)
#define POWER_LIMIT_STATUS_BIT (1 << 10)

static unsigned int msleep_time = 1000;
static struct timespec offset;

static int open_msr(int core) {
    char msr_filename[PATH_MAX];
    int fd;

    snprintf(msr_filename, PATH_MAX, "/dev/cpu/%d/msr", core);
    fd = open(msr_filename, O_RDONLY);
    if (fd < 0) {
        if (errno == ENXIO) {
            fprintf(stderr, "rdmsr: No CPU %d\n", core);
            exit(2);
        } else if (errno == EIO) {
            fprintf(stderr, "rdmsr: CPU %d doesn't support MSRs\n", core);
            exit(3);
        } else {
            perror("rdmsr:open");
            exit(127);
        }
    }
    return fd;
}

static long long read_msr(int fd, unsigned int which) {
    long long data;
    if (pread(fd, &data, sizeof data, which) != sizeof data) {
        perror("rdmsr:pread");
        fprintf(stderr, "Error reading MSR %x\n", which);
        exit(127);
    }
    return data;
}

#define MAX_CPUS 1024
#define MAX_PACKAGES 16

static int total_packages = 0;
static int package_map[MAX_PACKAGES];

static void detect_packages(void) {
    char filename[PATH_MAX];
    FILE *fff;
    int package;
    int i;

    for (i = 0; i < MAX_PACKAGES; i++) package_map[i] = -1;

    for (i = 0; i < MAX_CPUS; i++) {
        snprintf(filename, PATH_MAX, "/sys/devices/system/cpu/cpu%d/topology/physical_package_id", i);
        fff = fopen(filename, "r");
        if (fff == NULL) break;
        if (fscanf(fff, "%d", &package) != 1) {
            perror("read_package");
            exit(127);
        }
        fclose(fff);

        if (package >= MAX_PACKAGES) {
            fprintf(stderr, "Package ID %d exceeds maximum supported packages (%d)\n", package, MAX_PACKAGES);
            exit(127);
        }

        if (package_map[package] == -1) {
            total_packages++;
            package_map[package] = i;
        }
    }
}

static int check_system() {
    int fd = open_msr(0);
    if (fd < 0) {
        fprintf(stderr, "Couldn't open MSR 0\n");
        exit(1);
    }
    read_msr(fd, IA32_THERM_STATUS);
    close(fd);
    return 0;
}

static void measure_throttling() {
    int fd[total_packages];
    struct timeval now;
    long long result;
    int thermal_throttling_status;
    int power_limit_throttling_status;

    for (int i = 0; i < total_packages; i++) {
        fd[i] = open_msr(package_map[i]);
    }

    while (1) {
        for (int j = 0; j < total_packages; j++) {
            result = read_msr(fd[j], IA32_THERM_STATUS);
            thermal_throttling_status = 0;
            power_limit_throttling_status = 0;
            if (result & THERMAL_THROTTLING_STATUS_BIT) {
                thermal_throttling_status = 1;
            } 

            if (result & POWER_LIMIT_STATUS_BIT) {
                power_limit_throttling_status = 1;
            }

            get_adjusted_time(&now, &offset);
            printf("%ld%06ld %d %d Package_%d\n", now.tv_sec, now.tv_usec, thermal_throttling_status, power_limit_throttling_status, j);
        }
        usleep(msleep_time * 1000);
    }

    for (int l = 0; l < total_packages; l++) {
        close(fd[l]);
    }
}

int main(int argc, char **argv) {
    int c;
    bool check_system_flag = false;

    while ((c = getopt(argc, argv, "hi:c")) != -1) {
        switch (c) {
        case 'h':
            printf("Usage: %s [-h] [-i milliseconds] [-c]\n", argv[0]);
            exit(0);
        case 'i':
            msleep_time = parse_int(optarg);
            break;
        case 'c':
            check_system_flag = true;
            break;
        default:
            fprintf(stderr, "Unknown option %c\n", c);
            exit(-1);
        }
    }

    setvbuf(stdout, NULL, _IONBF, 0);
    detect_packages();

    if (check_system_flag) {
        exit(check_system());
    }

    get_time_offset(&offset);
    measure_throttling();

    return 0;
}
