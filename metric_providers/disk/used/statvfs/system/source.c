#include <stdio.h>
#include <sys/statvfs.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <sys/time.h>
#include <getopt.h>
#include "parse_int.h"

// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// in any case, none of these variables should change between threads
static unsigned int msleep_time=1000;

static unsigned long long get_disk_usage() {
    struct statvfs buf;

    // Query the root filesystem
    if (statvfs("/", &buf) == -1) {
        fprintf(stderr, "Couldn't issue statvfs() syscall\n");
        exit(1);
    }

    unsigned long long total_space = buf.f_blocks * buf.f_frsize;
    unsigned long long free_space = buf.f_bfree * buf.f_frsize; // by subtracting f_bfree instead of f_bavail we get what is used by non-root users which is more helpful

    return total_space - free_space;

}

static void output_stats() {

    struct timeval now;

    gettimeofday(&now, NULL);
    printf("%ld%06ld %llu\n", now.tv_sec, now.tv_usec, get_disk_usage());
    usleep(msleep_time*1000);

}

static int check_system() {
    struct statvfs buf;

    if (statvfs("/", &buf) == -1) {
        fprintf(stderr, "Couldn't issue statvfs() syscall\n");
        return 1;
    }

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
        output_stats();
    }

    return 0;
}
