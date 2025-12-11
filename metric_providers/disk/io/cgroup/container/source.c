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

static disk_io_t get_disk_cgroup(char* path, char* container_name) {
    unsigned long long int rbytes = 0;
    unsigned long long int wbytes = 0;
    unsigned int major_number;
    unsigned int minor_number;
    disk_io_t disk_io = {0};

    FILE * fd = fopen(path, "r");
    if ( fd == NULL) {
        fprintf(stderr, "Error - Could not open path %s (%s) for reading. Maybe the container is not running anymore? Errno: %d\n", path, container_name, errno);
        exit(1);
    }

    while (fscanf(fd, "%u:%u rbytes=%llu wbytes=%llu rios=%*u wios=%*u dbytes=%*u dios=%*u", &major_number, &minor_number, &rbytes, &wbytes) == 4) {

        // 1    Memory devices (e.g., /dev/mem, /dev/null)
        // 2    Floppy disk controller
        // 3    IDE hard disks (primary controller)
        // 7    Loopback devices (e.g., /dev/loop0)
        // 8    SCSI disks (including SATA and NVMe drives)
        // 9    Metadisk (RAID systems)
        // 11    SCSI CD-ROM (e.g., /dev/sr0)
        // 13    Input devices (e.g., /dev/input/event*)
        // 21    SCSI tape drives
        // 22    ESDI hard disks
        // 29    Network block devices (e.g., /dev/nbd)
        // 36    Accelerated Graphics Port (AGP)
        // 89    iSCSI devices
        // 116    ALSA (Advanced Linux Sound Architecture)
        // 180    USB devices
        // 202    Xen virtual block devices
        // 254    Device-mapper (e.g., LVM, cryptsetup)

        if (
            major_number == 1 || // 1    Memory devices (e.g., /dev/mem, /dev/null)
            major_number == 2 || // 2    Floppy disk controller
            major_number == 7 || // 7    Loopback devices (e.g., /dev/loop0)
            major_number == 11 || // 11    SCSI CD-ROM (e.g., /dev/sr0)
            major_number == 116 || // 116    ALSA (Advanced Linux Sound Architecture)
            major_number == 202 // 202    Xen virtual block devices
        ) {
            continue;
        }
        if (minor_number % 16 != 0) {
            fprintf(stderr, "Partion inside a docker container found. This should not happen: %u:%u rbytes=%llu wbytes=%llu\n", major_number, minor_number, rbytes, wbytes);
            exit(1);
        }
        disk_io.rbytes += rbytes;
        disk_io.wbytes += wbytes;
    }

    fclose(fd);

    // we initially had this check in the provider, but it very often happens that no io.stat file is produced if
    // the container has not written to disk so far.
    // erroring here thus seems to be the wrong way. Code left uncommented because we are still monitoring if this design choice is apt.
    //if(rbytes < 0 || wbytes < 0) {
    //    fprintf(stderr, "Error - io.stat could not be read or was < 0.");
    //    exit(1);
    //}

    return disk_io;
}

static void output_stats(container_t *containers, int length) {

    struct timeval now;
    int i;

    get_adjusted_time(&now, &offset);
    for(i=0; i<length; i++) {
        disk_io_t disk_io = get_disk_cgroup(containers[i].path, containers[i].name);
        printf("%ld%06ld %llu %llu %s\n", now.tv_sec, now.tv_usec, disk_io.rbytes, disk_io.wbytes, containers[i].id);
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

    while(1) {
        output_stats(containers, length);
    }

    free(containers); // since tools is only aborted by CTRL+C this is never called, but memory is freed on program end

    return 0;
}
