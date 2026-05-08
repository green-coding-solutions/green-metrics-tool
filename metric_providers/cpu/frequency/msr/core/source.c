#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <sys/sysinfo.h>
#include <sys/time.h>
#include <limits.h>
#include <stdbool.h>
#include <errno.h>
#include "gmt-lib.h"

#define MAX_CPUS 1024
#define MAX_PACKAGES 16

static unsigned int msleep_time = 1000;
static double base_ghz = 2.4;
static struct timespec offset;

static int total_cores = 0;
static int *cpu_map = NULL;

static int open_msr(int core) {
    char path[PATH_MAX];
    snprintf(path, PATH_MAX, "/dev/cpu/%d/msr", core);

    int fd = open(path, O_RDONLY);
    if (fd < 0) {
        if (errno == ENXIO) {
            fprintf(stderr, "No CPU %d\n", core);
            exit(2);
        } else if (errno == EIO) {
            fprintf(stderr, "CPU %d no MSR support\n", core);
            exit(3);
        } else {
            perror("open msr");
            exit(127);
        }
    }
    return fd;
}

static long long read_msr(int fd, unsigned int which) {
    long long data;
    if (pread(fd, &data, sizeof(data), which) != sizeof(data)) {
        perror("msr read");
        exit(127);
    }
    return data;
}

static void detect_cores(void) {
    cpu_map = malloc(sizeof(int) * MAX_CPUS);

    int id;
    char path[PATH_MAX];

    for (int i = 0; i < MAX_CPUS; i++) {
        snprintf(path, PATH_MAX, "/sys/devices/system/cpu/cpu%d/topology/core_id", i);

        FILE *f = fopen(path, "r");
        if (!f) continue; // CPU offline / non-contiguous numbering

        if (fscanf(f, "%d", &id) != 1) {
            fclose(f);
            fprintf(stderr, "Could not read cpu topology %s. Was expecting integer, found no match in file.\n", path);
            exit(127);
        }
        fclose(f);

        cpu_map[total_cores++] = i;
    }
}

static int test_msr(void) {
    int fd = open_msr(0);

    const int MSR_APERF = 0xE8;
    const int MSR_MPERF = 0xE7;

    long long a1 = read_msr(fd, MSR_APERF);
    long long m1 = read_msr(fd, MSR_MPERF);

    usleep(10000);

    long long a2 = read_msr(fd, MSR_APERF);
    long long m2 = read_msr(fd, MSR_MPERF);

    close(fd);

    if ((a2 == a1) || (m2 == m1)) {
        fprintf(stderr, "MSR test failed (no counter progression)\n");
        return -1;
    }

    return 0;
}

static void measure_freq(void) {
    int fd[total_cores];

    const int MSR_APERF = 0xE8;
    const int MSR_MPERF = 0xE7;

    uint64_t last_aperf[MAX_CPUS];
    uint64_t last_mperf[MAX_CPUS];

    for (int i = 0; i < total_cores; i++) {
        fd[i] = open_msr(cpu_map[i]);

        last_aperf[i] = read_msr(fd[i], MSR_APERF);
        last_mperf[i] = read_msr(fd[i], MSR_MPERF);
    }

    while (1) {
        usleep(msleep_time * 1000);

        for (int i = 0; i < total_cores; i++) {
            uint64_t a = read_msr(fd[i], MSR_APERF);
            uint64_t m = read_msr(fd[i], MSR_MPERF);

            uint64_t da = a - last_aperf[i];
            uint64_t dm = m - last_mperf[i];

            last_aperf[i] = a;
            last_mperf[i] = m;

            double ratio = (dm != 0) ? (double)da / (double)dm : 0.0;
            double freq_hz = base_ghz * ratio * 1e9;

            struct timeval now;
            get_adjusted_time(&now, &offset);

            uint64_t ts =
                (uint64_t)now.tv_sec * 1000000ULL +
                (uint64_t)now.tv_usec;

            printf("%llu %.0f %d\n",
                   (unsigned long long)ts,
                   freq_hz,
                   cpu_map[i]);
        }
    }
}

int main(int argc, char **argv) {
    int c;
    bool test_flag = false;

    while ((c = getopt(argc, argv, "hi:f:c")) != -1) {
        switch (c) {
        case 'h':
            printf("Usage: %s [-h] [-i msleep] [-f base_ghz] [-c]\n", argv[0]);
            exit(0);

        case 'i':
            msleep_time = parse_int(optarg);
            break;

        case 'f':
            base_ghz = parse_double(optarg);
            break;

        case 'c':
            test_flag = true;
            break;

        default:
            fprintf(stderr, "Unknown option %c\n", c);
            exit(-1);
        }
    }

    setvbuf(stdout, NULL, _IONBF, 0);

    detect_cores();

    get_time_offset(&offset);

    if (test_flag) {
        return test_msr();
    }

    measure_freq();
    return 0;
}