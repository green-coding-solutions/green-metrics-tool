#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <sys/time.h>
#include <time.h>
#include <string.h> // for strtok
#include <getopt.h>
#include <limits.h>
#include <stdbool.h>
#include <sys/stat.h>
#include "gmt-lib.h"
#include "gmt-container-lib.h"

typedef struct disk_io_t { // struct is a specification and this static makes no sense here
    unsigned long long int rbytes;
    unsigned long long int wbytes;
} disk_io_t;


// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// in any case, none of these variables should change between threads
static int user_id = -1;
static unsigned int msleep_time=1000;
static struct timespec offset;

// How many times to re-read io.stat when it comes back with an incomplete row,
// and how long to wait in between. Both windows are short on purpose: they only
// have to outlast a cgroup being wired up, and the provider must not drift off
// its sampling interval.
#define TORN_READ_RETRIES 3
#define TORN_READ_BACKOFF_US 20000
#define OPEN_RETRIES 5
#define OPEN_BACKOFF_US 20000

// Sums the rows of one io.stat for the devices we account for.
//
// Parsing is per line and only insists on the two fields we actually use. The
// row layout is not a stable kernel ABI - the discard counters (dbytes/dios)
// were added later - and the previous fscanf format had to match a row in
// full. On a row without those fields fscanf still returned 4, because all
// four assignments had happened, but left the stream mid-row, so every
// remaining device was silently dropped and the total came out too low.
//
// Sets *torn when a line carries a device prefix with no counters behind it.
// The kernel emits such a partial row while a cgroup is being set up, and it
// must not be read as "this container did no I/O": the sum is then missing a
// device, and publishing it would send the cumulative series backwards.
//
// An empty io.stat is NOT torn. It legitimately means the container has not
// touched a disk yet, and zero is the right answer for it.
static void parse_io_stat(FILE *fd, disk_io_t *out, bool *torn) {
    unsigned long long int rbytes = 0;
    unsigned long long int wbytes = 0;
    unsigned int major_number;
    unsigned int minor_number;
    disk_io_t disk_io = {0};
    char *line = NULL;
    size_t line_cap = 0;
    ssize_t line_len;

    *torn = false;

    while ((line_len = getline(&line, &line_cap, fd)) != -1) {
        if (sscanf(line, "%u:%u", &major_number, &minor_number) != 2) {
            if (line_len > 1) *torn = true; // a non-empty line we cannot even key on
            continue;
        }

        const char *rbytes_p = strstr(line, "rbytes=");
        const char *wbytes_p = strstr(line, "wbytes=");
        if (rbytes_p == NULL || wbytes_p == NULL) {
            *torn = true;
            continue;
        }
        rbytes = strtoull(rbytes_p + sizeof("rbytes=") - 1, NULL, 10);
        wbytes = strtoull(wbytes_p + sizeof("wbytes=") - 1, NULL, 10);

        // 1    Memory devices (e.g., /dev/mem, /dev/null)
        // 2    Floppy disk controller
        // 3    IDE hard disks (primary controller)
        // 7    Loopback devices (e.g., /dev/loop0)
        // 8    SCSI disks (including SATA and network storage via ISCSI)
        // 9    Metadisk (RAID systems)
        // 11    SCSI CD-ROM (e.g., /dev/sr0)
        // 13    Input devices (e.g., /dev/input/event*)
        // 21    SCSI tape drives
        // 22    ESDI hard disks
        // 29    Network block devices (e.g., /dev/nbd)
        // 36    Accelerated Graphics Port (AGP)
        // 43    Network Block Device (also used in macOS Docker VM)
        // 89    iSCSI devices
        // 116    ALSA (Advanced Linux Sound Architecture)
        // 180    USB devices
        // 202    Xen virtual block devices
        // 251-254 Static Device-mapper (e.g., LVM, cryptsetup)
        // 259 NVME
        // 260–300 Dynamic block mappers (Zoned devices, NVME alternatives)

        // => If this code runs into trouble in the future we might need to migrate to a better detection mechanism
        // However lsblk -o NAME,MAJ:MIN,TYPE is not too helpful, as the type is not useful to use
        // (resolves to sysfs virtual / physical classification)
        // but especially the dynamic device block mapper might contain unknown disk we want to track or exclude
        // we will touch this when errors are reported :)

        ///////////////////// Guideline ///////////////////////////
        // This code should only detect non-partitions and only the main disk, as this is where data is effectively stored
        // This includes network storage as well (as in the end a physical disk is somewhere) - Thus the physical / virtual
        // distinciton of the sysfs is not too helpful for us.
        // Disk that reside in memory though should NOT be detected as this is already covered by the memory provider

        if (
            major_number == 1 || // 1    Memory devices (e.g., /dev/mem, /dev/null)
            major_number == 2 || // 2    Floppy disk controller
            major_number == 7 || // 7    Loopback devices (e.g., /dev/loop0)
            major_number == 11 || // 11    SCSI CD-ROM (e.g., /dev/sr0)
            major_number == 116 || // 116    ALSA (Advanced Linux Sound Architecture)
            major_number == 202 || // 202    Xen virtual block devices
            major_number == 251 || // Device Mapper
            major_number == 252 || // Device Mapper
            major_number == 253 || // Device Mapper
            major_number == 254 // Device Mapper
        ) {
            continue;
        }

        if (is_partition_sysfs(major_number, minor_number)) {
            fprintf(stderr, "Partition inside a docker container found. This should not happen: %u:%u rbytes=%llu wbytes=%llu\n", major_number, minor_number, rbytes, wbytes);
            exit(1);
        }
        disk_io.rbytes += rbytes;
        disk_io.wbytes += wbytes;
    }

    free(line);
    *out = disk_io;
}

// Reads io.stat, retrying briefly on the two transient states the cgroup goes
// through while it is being (re)created: the file not being there at all, and
// the file holding a half-written row. Returns false if it never got a clean
// read, in which case *out must not be published.
static bool read_disk_cgroup(char* path, char* container_name, disk_io_t* out) {
    int attempt;

    for (attempt = 0; ; attempt++) {
        FILE *fd = NULL;
        int open_attempt;
        bool torn = false;

        for (open_attempt = 0; open_attempt < OPEN_RETRIES; open_attempt++) {
            fd = fopen(path, "r");
            if (fd != NULL) break;
            // A container's scope directory briefly disappears when it is
            // recreated, so do not call the container dead on the first miss.
            usleep(OPEN_BACKOFF_US);
        }
        if (fd == NULL) {
            fprintf(stderr, "Error - Could not open path %s (%s) for reading. Maybe the container is not running anymore? Errno: %d\n", path, container_name, errno);
            exit(1);
        }

        parse_io_stat(fd, out, &torn);
        fclose(fd);

        if (!torn) return true;
        if (attempt >= TORN_READ_RETRIES) return false;
        usleep(TORN_READ_BACKOFF_US);
    }
}

// Per container measurement state.
//
// io.stat counters are cumulative, but only for as long as that particular
// cgroup object lives. Restarting a container destroys the scope and recreates
// it at the SAME path with counters starting again at zero - and the path is
// resolved exactly once, in parse_containers(), so this provider keeps reading
// straight through it. Publishing the raw value then rewinds the series and
// disk_io_parse.py rejects the entire measurement for negative intervals, long
// after the scenario itself has finished successfully.
//
// So what we publish is carry + last_raw: `carry` holds the final totals of
// every previous incarnation of the cgroup, `last_raw` the newest trusted
// reading from the current one. Incarnations are told apart by the io.stat
// inode, which changes exactly when the cgroup is recreated.
typedef struct container_state_t {
    bool have_ident;
    dev_t dev;
    ino_t ino;
    disk_io_t carry;
    disk_io_t last_raw;
} container_state_t;

static container_state_t *container_states = NULL;

static void output_stats(container_t *containers, int length) {

    struct timeval now;
    int i;

    get_adjusted_time(&now, &offset);
    for(i=0; i<length; i++) {
        container_state_t *state = &container_states[i];
        struct stat sb;
        disk_io_t raw = {0};

        // Check identity before reading, so a fresh set of counters is never
        // compared against the previous incarnation's.
        if (stat(containers[i].path, &sb) == 0) {
            if (!state->have_ident) {
                state->dev = sb.st_dev;
                state->ino = sb.st_ino;
                state->have_ident = true;
            } else if (sb.st_dev != state->dev || sb.st_ino != state->ino) {
                fprintf(stderr,
                        "Warning - cgroup for %s (%s) was recreated, so its io.stat counters restart at zero. "
                        "Carrying over rbytes=%llu wbytes=%llu.\n",
                        containers[i].name, containers[i].path,
                        state->last_raw.rbytes, state->last_raw.wbytes);
                state->carry.rbytes += state->last_raw.rbytes;
                state->carry.wbytes += state->last_raw.wbytes;
                state->last_raw.rbytes = 0;
                state->last_raw.wbytes = 0;
                state->dev = sb.st_dev;
                state->ino = sb.st_ino;
            }
        }

        if (!read_disk_cgroup(containers[i].path, containers[i].name, &raw)) {
            // Still an incomplete row after retrying, so the sum is missing a
            // device. Republish the last trusted reading rather than a value we
            // already know is too low.
            fprintf(stderr,
                    "Warning - io.stat for %s (%s) still held an incomplete row after retrying; "
                    "reusing last trusted reading (rbytes=%llu wbytes=%llu).\n",
                    containers[i].name, containers[i].path,
                    state->last_raw.rbytes, state->last_raw.wbytes);
        } else if (raw.rbytes < state->last_raw.rbytes || raw.wbytes < state->last_raw.wbytes) {
            // A live kernel counter cannot decrease within one incarnation, and
            // a recreated cgroup was already handled above. Whatever this is, it
            // is not a reading we can publish.
            fprintf(stderr,
                    "Warning - io.stat for %s (%s) went backwards (rbytes=%llu->%llu wbytes=%llu->%llu) "
                    "without the cgroup being recreated; reusing last trusted reading.\n",
                    containers[i].name, containers[i].path,
                    state->last_raw.rbytes, raw.rbytes, state->last_raw.wbytes, raw.wbytes);
        } else {
            state->last_raw = raw;
        }

        printf("%ld%06ld %llu %llu %s\n", now.tv_sec, now.tv_usec,
               state->carry.rbytes + state->last_raw.rbytes,
               state->carry.wbytes + state->last_raw.wbytes,
               containers[i].id);
    }
    usleep(msleep_time*1000);
}


int main(int argc, char **argv) {

    int c;
    bool check_system_flag = false;
    int optarg_len;
    char *containers_string = NULL;  // Dynamic buffer to store optarg
    container_t *containers = NULL;

    setvbuf(stdout, NULL, _IONBF, 0);
    user_id = getuid();

    static struct option long_options[] =
    {
        {"help", no_argument, NULL, 'h'},
        {"interval", no_argument, NULL, 'i'},
        {"containers", no_argument, NULL, 's'},
        {"check", no_argument, NULL, 'c'},
        {NULL, 0, NULL, 0}
    };

    while ((c = getopt_long(argc, argv, "i:s:hc", long_options, NULL)) != -1) {
        switch (c) {
        case 'h':
            printf("Usage: %s [-i msleep_time] [-h]\n\n",argv[0]);
            printf("\t-h      : displays this help\n");
            printf("\t-s      : string of container IDs or cgroup names separated by comma\n");
            printf("\t-i      : specifies the milliseconds sleep time that will be slept between measurements\n");
            printf("\t-c      : check system and exit\n");
            printf("\n");
            exit(0);
        case 'i':
            msleep_time = parse_int(optarg);
            break;
        case 's':
            optarg_len = strlen(optarg);
            containers_string = (char *)malloc(optarg_len + 1);  // Allocate memory
            if (!containers_string) {
                fprintf(stderr, "Could not allocate memory for containers string\n");
                exit(1);
            }
            memcpy(containers_string, optarg, optarg_len);
            containers_string[optarg_len] = '\0'; // Ensure NUL termination if max length
            break;
        case 'c':
            check_system_flag = true;
            break;
        default:
            fprintf(stderr,"Unknown option %c\n",c);
            exit(-1);
        }
    }

    if(check_system_flag){
        exit(check_path("/sys/fs/cgroup/io.stat"));
    }

    get_time_offset(&offset);

    int length = parse_containers("io.stat", user_id, &containers, containers_string, false);

    container_states = calloc(length, sizeof(container_state_t));
    if (container_states == NULL) {
        fprintf(stderr, "Could not allocate memory for container states\n");
        exit(1);
    }

    while(1) {
        output_stats(containers, length);
    }

    free(containers); // since tools is only aborted by CTRL+C this is never called, but memory is freed on program end

    return 0;
}
