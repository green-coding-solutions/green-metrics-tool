#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <sys/time.h>
#include <string.h> // for strtok
#include <getopt.h>
#include <limits.h>
#include <sys/ioctl.h>
#include <linux/fs.h>
#include "parse_int.h"

// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// in any case, none of these variables should change between threads
static unsigned int msleep_time=1000;

static void output_get_disk_procfs() {
    unsigned long long int sectors_read = 0;
    unsigned long long int sectors_written = 0;
    int minor_number;
    int major_number;
    char device_name[16];
    int match_result = 0;
    char buf[1024];
    struct timeval now;

    FILE * fd = fopen("/proc/diskstats", "r");
    if ( fd == NULL) {
        fprintf(stderr, "Error - Could not open /proc/diskstats for reading. Errno: %d\n", errno);
        exit(1);
    }

    gettimeofday(&now, NULL); // one call for get time of day for all interfaces is fine. The overhead would be more than the gain in granularity

    while (fgets(buf, 1024, fd)) {
        // We are not counting dropped packets, as we believe they will at least show up in the
        // sender side as not dropped.
        // Since we are iterating over all relevant docker containers we should catch these packets at least in one /proc/net/dev file
        match_result = sscanf(buf, "%u %u %15s %*u %*u %llu %*u %*u %*u %llu", &major_number, &minor_number, device_name, &sectors_read, &sectors_written);
        if (match_result != 5) {
            fprintf(stderr, "Could not match /proc/diskstats pattern in %s. Amount was %d\n", buf, match_result);
            exit(1);
        }


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
            continue; // we skip when we have found a non root level device (aka partition)
        }

        printf("%ld%06ld %llu %llu %s\n", now.tv_sec, now.tv_usec, sectors_read, sectors_written, device_name);
    }

    usleep(msleep_time*1000); // after we have looked at all interfaces

    fclose(fd);
}


static int check_system() {
    FILE* fd = fopen("/proc/diskstats", "r");

    if (fd == NULL) {
        fprintf(stderr, "Couldn't open /proc/diskstats file.\n");
        return 1;
    }
    fclose(fd);

    return 0;
}

int main(int argc, char **argv) {

    int c;
    int check_system_flag = 0;

    setvbuf(stdout, NULL, _IONBF, 0);

    static struct option long_options[] =
    {
        {"help", no_argument, NULL, 'h'},
        {"interval", no_argument, NULL, 'i'},
        {"check", no_argument, NULL, 'c'},
        {NULL, 0, NULL, 0}
    };

    while ((c = getopt_long(argc, argv, "i:hc", long_options, NULL)) != -1) {
        switch (c) {
        case 'h':
            printf("Usage: %s [-i msleep_time] [-h]\n\n",argv[0]);
            printf("\t-h      : displays this help\n");
            printf("\t-i      : specifies the milliseconds sleep time that will be slept between measurements\n");
            printf("\t-c      : check system and exit\n\n");
            exit(0);
        case 'i':
            msleep_time = parse_int(optarg);
            break;
        case 'c':
            check_system_flag = 1;
            break;
        default:
            fprintf(stderr,"Unknown option %c\n",c);
            exit(-1);
        }
    }

    if(check_system_flag){
        exit(check_system());
    }

    while(1) {
        output_get_disk_procfs();
    }

    return 0;
}
