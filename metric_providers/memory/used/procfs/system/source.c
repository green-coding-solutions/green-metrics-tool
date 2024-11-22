#include <stdio.h>
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

static unsigned long long int get_memory_procfs() {

    // cat /proc/meminfo
    // MemTotal:       32646584 kB
    // MemFree:        28813256 kB
    // MemAvailable:   30162336 kB

    unsigned long long int mem_total = 0;
    unsigned long long int mem_available = 0;
    unsigned long long int mem_used = 0;
    int match_result = 0;
    char buf[200];

    FILE * fd = fopen("/proc/meminfo", "r");
    if ( fd == NULL) {
        fprintf(stderr, "Error - Could not open /proc/meminfo for reading\n");
        exit(1);
    }

    if (fgets(buf, 200, fd) == NULL) {
        fprintf(stderr, "Error or EOF encountered while reading input.\n");
        exit(1);
    }

    match_result = sscanf(buf, "MemTotal: %llu kB", &mem_total);
    if (match_result != 1) {
        fprintf(stderr, "Error - MemTotal could not be matched in /proc/meminfo\n");
        exit(1);
    }

    if (fgets(buf, 200, fd) == NULL || fgets(buf, 200, fd) == NULL) {
        fprintf(stderr, "Error or EOF encountered while reading input.\n");
        exit(1);
    }
    match_result = sscanf(buf, "MemAvailable: %llu kB", &mem_available);
    if (match_result != 1) {
        fprintf(stderr, "Error - MemAvailable could not be matched in /proc/meminfo\n");
        exit(1);
    }

    // note that here we need to use 1024 instead of 1000 as we are already coming from kiB and not kB
    mem_used = (mem_total - mem_available) * 1024; // outputted value is in Bytes then

    fclose(fd);

    if(mem_used <= 0) {
        fprintf(stderr, "Error - /proc/meminfo was <= 0. Value: %llu\n", mem_used);
        exit(1);
    }

    return mem_used;

}

static void output_stats() {

    struct timeval now;

    gettimeofday(&now, NULL);
    printf("%ld%06ld %llu\n", now.tv_sec, now.tv_usec, get_memory_procfs());
    usleep(msleep_time*1000);

}

static int check_system() {

    FILE* fd = fopen("/proc/meminfo", "r");

    if (fd == NULL) {
        fprintf(stderr, "Couldn't open /proc/meminfo file\n");
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
        output_stats();
    }

    return 0;
}
