#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <errno.h>
#include <unistd.h>
#include <limits.h>
#include <stdbool.h>
#include <sys/syscall.h>
#include <sys/time.h>
#include <linux/perf_event.h>
#include "gmt-lib.h"

/*
 * Reports CPU frequencies via the perf_event_open() interface.
 *
 * Core (always):
 *   Per CPU APERF / MPERF from the kernel's "msr" PMU (free running, works on Intel and AMD,
 *   does not occupy general purpose counters).
 *   frequency [Hz] = base_ghz * 1e9 * delta(aperf) / delta(mperf)
 *
 * Uncore (-u):
 *   Uncore clockticks per uncore domain (package or die) from an uncore PMU.
 *   frequency [Hz] = delta(clockticks) / delta(time_running) [ns] * 1e9
 *   Using time_running from the kernel also takes care of counter multiplexing.
 *
 *   The uncore PMU that exposes clockticks differs between Intel generations. We try a list
 *   of known PMU / event combinations. PMU and event can also be passed with -p and -e.
 */

#define SYSFS_PMU_DIR "/sys/bus/event_source/devices"
#define MAX_CPUS 1024
#define MAX_DOMAINS 64
#define MAX_EVENT_STR 256
#define MAX_LABEL 64

// Plausibility range for the uncore -c check, to detect PMU events that do not count uncore clocks
#define MIN_PLAUSIBLE_HZ 100000000.0   // 100 MHz
#define MAX_PLAUSIBLE_HZ 10000000000.0 // 10 GHz

struct pmu_event {
    int type;
    uint64_t config;
};

struct uncore_candidate {
    const char *pmu;
    const char *event_name; // name in <pmu>/events/ (preferred)
    const char *raw_event;  // used if event_name is NULL
};

static const struct uncore_candidate uncore_candidates[] = {
    {"uncore_clock", "clockticks", NULL}, // client: Ice Lake and newer
    {"uncore_cbox_0", "clockticks", NULL}, // client: Sandy Bridge .. Comet Lake (fixed UNC_CLOCK counter)
    {"uncore_ubox", NULL, "event=0xff"},   // server: fixed UCLK counter (Haswell-EP and newer)
    {"uncore_cha_0", "clockticks", NULL},  // server: CHA clockticks, if the kernel exposes the alias
};

struct core {
    int cpu;
    int aperf_fd;
    int mperf_fd;
    uint64_t last_aperf;
    uint64_t last_mperf;
};

struct uncore_domain {
    int cpu;
    int fd;
    char label[MAX_LABEL];
    uint64_t last_value;
    uint64_t last_running;
};

struct uncore_read_format {
    uint64_t value;
    uint64_t time_enabled;
    uint64_t time_running;
};

static unsigned int msleep_time = 1000;
static double base_ghz = 2.4;
static bool uncore_flag = false;
static struct timespec offset;

static struct pmu_event aperf_event, mperf_event;
static struct core cores[MAX_CPUS];
static int total_cores = 0;

static char uncore_pmu_name[NAME_MAX] = {0};
static char uncore_event_str[MAX_EVENT_STR] = {0};
static struct pmu_event uncore_event;
static struct uncore_domain domains[MAX_DOMAINS];
static int total_domains = 0;

static long perf_event_open(struct perf_event_attr *attr, pid_t pid, int cpu, int group_fd, unsigned long flags) {
    return syscall(SYS_perf_event_open, attr, pid, cpu, group_fd, flags);
}

// reads the first line of a file into buf. Returns 0 on success
static int read_line(const char *path, char *buf, size_t len) {
    FILE *f = fopen(path, "r");
    if (!f) return -1;
    if (!fgets(buf, (int)len, f)) {
        fclose(f);
        return -1;
    }
    fclose(f);
    buf[strcspn(buf, "\n")] = '\0';
    return 0;
}

static int read_int_file(const char *path, int *out) {
    char buf[64];
    if (read_line(path, buf, sizeof(buf)) != 0) return -1;
    char *end;
    long v = strtol(buf, &end, 10);
    if (end == buf) return -1;
    *out = (int)v;
    return 0;
}

static bool pmu_exists(const char *pmu) {
    char path[PATH_MAX];
    snprintf(path, PATH_MAX, SYSFS_PMU_DIR "/%s/type", pmu);
    return access(path, R_OK) == 0;
}

/*
 * Places `value` into config according to a sysfs format spec like
 * "config:0-7" or "config:0-7,21" or "config:24". Only `config` is supported.
 */
static int apply_format(const char *format, uint64_t value, uint64_t *config) {
    if (strncmp(format, "config:", 7) != 0) {
        fprintf(stderr, "Unsupported PMU format '%s' (only 'config' is supported)\n", format);
        return -1;
    }

    char spec[128];
    snprintf(spec, sizeof(spec), "%s", format + 7);

    int value_bit = 0;
    char *saveptr = NULL;
    for (char *tok = strtok_r(spec, ",", &saveptr); tok; tok = strtok_r(NULL, ",", &saveptr)) {
        int lo, hi;
        if (sscanf(tok, "%d-%d", &lo, &hi) != 2) {
            if (sscanf(tok, "%d", &lo) != 1) {
                fprintf(stderr, "Could not parse PMU format '%s'\n", format);
                return -1;
            }
            hi = lo;
        }
        if (lo < 0 || hi > 63 || lo > hi) {
            fprintf(stderr, "Invalid bit range in PMU format '%s'\n", format);
            return -1;
        }
        for (int bit = lo; bit <= hi; bit++, value_bit++) {
            if (value_bit < 64 && (value >> value_bit) & 1ULL) {
                *config |= (1ULL << bit);
            }
        }
    }
    return 0;
}

// turns "event=0xff,umask=0x00" into a perf event using the PMU's type and format/ directory
static int encode_event(const char *pmu, const char *event, struct pmu_event *out) {
    char path[PATH_MAX];
    snprintf(path, PATH_MAX, SYSFS_PMU_DIR "/%s/type", pmu);
    if (read_int_file(path, &out->type) != 0) {
        fprintf(stderr, "Could not read PMU type from %s\n", path);
        return -1;
    }

    char buf[MAX_EVENT_STR];
    snprintf(buf, sizeof(buf), "%s", event);

    out->config = 0;
    char *saveptr = NULL;
    for (char *term = strtok_r(buf, ",", &saveptr); term; term = strtok_r(NULL, ",", &saveptr)) {
        char *eq = strchr(term, '=');
        uint64_t value = 1; // a bare term like "edge" means 1
        if (eq) {
            *eq = '\0';
            char *end;
            value = strtoull(eq + 1, &end, 0);
            if (end == eq + 1) {
                fprintf(stderr, "Could not parse value of event term '%s'\n", term);
                return -1;
            }
        }

        char format[128];
        snprintf(path, PATH_MAX, SYSFS_PMU_DIR "/%s/format/%s", pmu, term);
        if (read_line(path, format, sizeof(format)) != 0) {
            fprintf(stderr, "PMU %s has no format term '%s'\n", pmu, term);
            return -1;
        }
        if (apply_format(format, value, &out->config) != 0) return -1;
    }
    return 0;
}

// encodes the named event from <pmu>/events/<name>
static int encode_named_event(const char *pmu, const char *name, struct pmu_event *out) {
    char path[PATH_MAX];
    char event[MAX_EVENT_STR];
    snprintf(path, PATH_MAX, SYSFS_PMU_DIR "/%s/events/%s", pmu, name);
    if (read_line(path, event, sizeof(event)) != 0) {
        fprintf(stderr, "PMU %s has no event '%s' (%s)\n", pmu, name, path);
        return -1;
    }
    return encode_event(pmu, event, out);
}

static int open_event(const struct pmu_event *ev, int cpu, uint64_t read_format, const char *what) {
    struct perf_event_attr attr;
    memset(&attr, 0, sizeof(attr));
    attr.size = sizeof(attr);
    attr.type = (uint32_t)ev->type;
    attr.config = ev->config;
    attr.read_format = read_format;
    // msr and uncore PMUs do not support sampling or exclude_* flags

    int fd = (int)perf_event_open(&attr, -1, cpu, -1, 0);
    if (fd < 0) {
        fprintf(stderr, "perf_event_open failed for %s (type %d, config 0x%llx) on CPU %d: %s\n",
                what, ev->type, (unsigned long long)ev->config, cpu, strerror(errno));
        if (errno == EACCES || errno == EPERM) {
            fprintf(stderr, "Binary needs to run as root (setuid) or with CAP_PERFMON, or /proc/sys/kernel/perf_event_paranoid must be <= 0\n");
        }
        exit(1);
    }
    return fd;
}

static uint64_t read_u64(int fd) {
    uint64_t v;
    if (read(fd, &v, sizeof(v)) != sizeof(v)) {
        perror("perf counter read");
        exit(1);
    }
    return v;
}

/* ---------------- core ---------------- */

static void detect_cores(void) {
    char path[PATH_MAX];
    int id;

    for (int i = 0; i < MAX_CPUS; i++) {
        snprintf(path, PATH_MAX, "/sys/devices/system/cpu/cpu%d/topology/core_id", i);
        if (read_int_file(path, &id) != 0) continue; // CPU offline / non-contiguous numbering

        cores[total_cores].cpu = i;
        cores[total_cores].aperf_fd = -1;
        cores[total_cores].mperf_fd = -1;
        total_cores++;
    }

    if (total_cores == 0) {
        fprintf(stderr, "No CPU cores detected\n");
        exit(1);
    }
}

static void resolve_core_events(void) {
    if (!pmu_exists("msr")) {
        fprintf(stderr, "perf msr PMU not found in " SYSFS_PMU_DIR ". Are you running in a VM?\n");
        exit(1);
    }
    if (encode_named_event("msr", "aperf", &aperf_event) != 0) exit(1);
    if (encode_named_event("msr", "mperf", &mperf_event) != 0) exit(1);
}

static void open_cores(void) {
    for (int i = 0; i < total_cores; i++) {
        cores[i].aperf_fd = open_event(&aperf_event, cores[i].cpu, 0, "msr/aperf");
        cores[i].mperf_fd = open_event(&mperf_event, cores[i].cpu, 0, "msr/mperf");
        cores[i].last_aperf = read_u64(cores[i].aperf_fd);
        cores[i].last_mperf = read_u64(cores[i].mperf_fd);
    }
}

static double sample_core(struct core *c) {
    uint64_t a = read_u64(c->aperf_fd);
    uint64_t m = read_u64(c->mperf_fd);

    uint64_t da = a - c->last_aperf;
    uint64_t dm = m - c->last_mperf;
    c->last_aperf = a;
    c->last_mperf = m;

    double ratio = (dm != 0) ? (double)da / (double)dm : 0.0;
    return base_ghz * ratio * 1e9;
}

/* ---------------- uncore ---------------- */

// fills uncore_pmu_name, uncore_event_str, uncore_event
static void resolve_uncore_event(void) {
    char path[PATH_MAX];

    if (uncore_pmu_name[0] == '\0') { // auto discovery
        size_t n = sizeof(uncore_candidates) / sizeof(uncore_candidates[0]);
        for (size_t i = 0; i < n; i++) {
            if (!pmu_exists(uncore_candidates[i].pmu)) continue;

            if (uncore_candidates[i].event_name) {
                snprintf(path, PATH_MAX, SYSFS_PMU_DIR "/%s/events/%s", uncore_candidates[i].pmu, uncore_candidates[i].event_name);
                if (read_line(path, uncore_event_str, sizeof(uncore_event_str)) != 0) continue;
            } else {
                snprintf(uncore_event_str, sizeof(uncore_event_str), "%s", uncore_candidates[i].raw_event);
            }
            snprintf(uncore_pmu_name, sizeof(uncore_pmu_name), "%s", uncore_candidates[i].pmu);
            break;
        }
        if (uncore_pmu_name[0] == '\0') {
            fprintf(stderr, "No supported uncore PMU with a clockticks event found in " SYSFS_PMU_DIR ". "
                            "Uncore reporting only supports Intel CPUs on bare metal. "
                            "You can specify the PMU and event manually with -p and -e.\n");
            exit(1);
        }
    } else {
        if (!pmu_exists(uncore_pmu_name)) {
            fprintf(stderr, "PMU %s does not exist in " SYSFS_PMU_DIR "\n", uncore_pmu_name);
            exit(1);
        }
        if (uncore_event_str[0] == '\0') {
            snprintf(path, PATH_MAX, SYSFS_PMU_DIR "/%s/events/clockticks", uncore_pmu_name);
            if (read_line(path, uncore_event_str, sizeof(uncore_event_str)) != 0) {
                fprintf(stderr, "PMU %s has no 'clockticks' event. Please specify one with -e\n", uncore_pmu_name);
                exit(1);
            }
        }
    }

    if (encode_event(uncore_pmu_name, uncore_event_str, &uncore_event) != 0) exit(1);
}

static void build_uncore_label(int cpu, char *label, size_t len) {
    char path[PATH_MAX];
    int package = -1, die = -1;

    snprintf(path, PATH_MAX, "/sys/devices/system/cpu/cpu%d/topology/physical_package_id", cpu);
    read_int_file(path, &package);
    snprintf(path, PATH_MAX, "/sys/devices/system/cpu/cpu%d/topology/die_id", cpu);
    read_int_file(path, &die);

    snprintf(label, len, "Uncore_Package_%d_Die_%d", package, die < 0 ? 0 : die);
}

// the uncore PMU's cpumask has one CPU per uncore domain (package or die), e.g. "0,56" or "0-1"
static void detect_uncore_domains(void) {
    char path[PATH_MAX];
    char mask[1024];

    snprintf(path, PATH_MAX, SYSFS_PMU_DIR "/%s/cpumask", uncore_pmu_name);
    if (read_line(path, mask, sizeof(mask)) != 0) {
        // PMUs without cpumask are not uncore PMUs
        fprintf(stderr, "Could not read %s\n", path);
        exit(1);
    }

    char *saveptr = NULL;
    for (char *tok = strtok_r(mask, ",", &saveptr); tok; tok = strtok_r(NULL, ",", &saveptr)) {
        int lo, hi;
        if (sscanf(tok, "%d-%d", &lo, &hi) != 2) {
            if (sscanf(tok, "%d", &lo) != 1) {
                fprintf(stderr, "Could not parse cpumask '%s'\n", tok);
                exit(1);
            }
            hi = lo;
        }
        for (int cpu = lo; cpu <= hi; cpu++) {
            if (total_domains >= MAX_DOMAINS) {
                fprintf(stderr, "More than %d uncore domains found\n", MAX_DOMAINS);
                exit(1);
            }
            domains[total_domains].cpu = cpu;
            domains[total_domains].fd = -1;
            build_uncore_label(cpu, domains[total_domains].label, MAX_LABEL);
            total_domains++;
        }
    }

    if (total_domains == 0) {
        fprintf(stderr, "No CPUs found in %s\n", path);
        exit(1);
    }

    // Shorten label to Uncore_Package_X if there is only one die per package
    bool multi_die = false;
    for (int i = 0; i < total_domains; i++) {
        if (strstr(domains[i].label, "_Die_0") == NULL) multi_die = true;
    }
    if (!multi_die) {
        for (int i = 0; i < total_domains; i++) {
            char *p = strstr(domains[i].label, "_Die_");
            if (p) *p = '\0';
        }
    }
}

static void read_uncore(struct uncore_domain *d, struct uncore_read_format *rf) {
    if (read(d->fd, rf, sizeof(*rf)) != sizeof(*rf)) {
        perror("perf uncore counter read");
        exit(1);
    }
}

static void open_uncore(void) {
    for (int i = 0; i < total_domains; i++) {
        domains[i].fd = open_event(&uncore_event, domains[i].cpu,
                                   PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING,
                                   uncore_pmu_name);
        struct uncore_read_format rf;
        read_uncore(&domains[i], &rf);
        domains[i].last_value = rf.value;
        domains[i].last_running = rf.time_running;
    }
}

// computes the uncore frequency since the last call. Returns false if counter did not run in the interval
static bool sample_uncore(struct uncore_domain *d, double *hz) {
    struct uncore_read_format rf;
    read_uncore(d, &rf);

    uint64_t d_value = rf.value - d->last_value;
    uint64_t d_running = rf.time_running - d->last_running;
    d->last_value = rf.value;
    d->last_running = rf.time_running;

    if (d_running == 0) return false;

    *hz = (double)d_value * 1e9 / (double)d_running;
    return true;
}

/* ---------------- main ---------------- */

static int check_system(void) {
    open_cores();
    if (uncore_flag) open_uncore();

    usleep(50000);

    double hz = sample_core(&cores[0]);
    if (hz <= 0) {
        fprintf(stderr, "perf msr/aperf and msr/mperf did not progress on CPU %d\n", cores[0].cpu);
        return 1;
    }

    for (int i = 0; i < total_domains; i++) {
        if (!sample_uncore(&domains[i], &hz)) {
            fprintf(stderr, "Uncore counter on %s did not run (multiplexed away or not scheduled)\n", domains[i].label);
            return 1;
        }
        if (hz < MIN_PLAUSIBLE_HZ || hz > MAX_PLAUSIBLE_HZ) {
            fprintf(stderr, "Implausible uncore frequency %.0f Hz on %s from PMU %s event '%s'. "
                            "The event probably does not count uncore clockticks on this CPU. Specify the correct one with -p / -e\n",
                    hz, domains[i].label, uncore_pmu_name, uncore_event_str);
            return 1;
        }
    }
    return 0;
}

static void measure_freq(void) {
    struct timeval now;

    open_cores();
    if (uncore_flag) open_uncore();

    while (1) {
        usleep(msleep_time * 1000);

        for (int i = 0; i < total_cores; i++) {
            double hz = sample_core(&cores[i]);

            get_adjusted_time(&now, &offset);
            printf("%ld%06ld %.0f Core_%d\n", now.tv_sec, now.tv_usec, hz, cores[i].cpu);
        }

        for (int i = 0; i < total_domains; i++) {
            double hz;
            if (!sample_uncore(&domains[i], &hz)) continue; // no data for this interval

            get_adjusted_time(&now, &offset);
            printf("%ld%06ld %.0f %s\n", now.tv_sec, now.tv_usec, hz, domains[i].label);
        }
    }
}

int main(int argc, char **argv) {
    int c;
    bool check_system_flag = false;

    while ((c = getopt(argc, argv, "hi:f:cup:e:")) != -1) {
        switch (c) {
        case 'h':
            printf("Usage: %s [-h] [-i milliseconds] [-f base_ghz] [-c] [-u [-p pmu] [-e event]]\n", argv[0]);
            printf("\t-h      : displays this help\n");
            printf("\t-i      : specifies the milliseconds sleep time that will be slept between measurements\n");
            printf("\t-f      : nominal (non-turbo) base clock of the CPU in GHz (default: 2.4)\n");
            printf("\t-c      : check system and exit\n");
            printf("\t-u      : additionally report the uncore frequency (Intel only)\n");
            printf("\t-p      : uncore PMU name in " SYSFS_PMU_DIR " (default: auto-detect)\n");
            printf("\t-e      : event terms for the uncore PMU, e.g. 'event=0xff' (default: the PMU's clockticks event)\n\n");
            exit(0);
        case 'i':
            msleep_time = parse_int(optarg);
            break;
        case 'f':
            base_ghz = parse_double(optarg);
            break;
        case 'c':
            check_system_flag = true;
            break;
        case 'u':
            uncore_flag = true;
            break;
        case 'p':
            snprintf(uncore_pmu_name, sizeof(uncore_pmu_name), "%s", optarg);
            break;
        case 'e':
            snprintf(uncore_event_str, sizeof(uncore_event_str), "%s", optarg);
            break;
        default:
            fprintf(stderr, "Unknown option %c\n", c);
            exit(-1);
        }
    }

    if ((uncore_pmu_name[0] != '\0' || uncore_event_str[0] != '\0') && !uncore_flag) {
        fprintf(stderr, "-p and -e require -u\n");
        exit(1);
    }
    if (uncore_event_str[0] != '\0' && uncore_pmu_name[0] == '\0') {
        fprintf(stderr, "-e requires -p\n");
        exit(1);
    }

    setvbuf(stdout, NULL, _IONBF, 0);

    detect_cores();
    resolve_core_events();

    if (uncore_flag) {
        resolve_uncore_event();
        detect_uncore_domains();
    }

    if (check_system_flag) {
        exit(check_system());
    }

    get_time_offset(&offset);
    measure_freq();

    return 0;
}
