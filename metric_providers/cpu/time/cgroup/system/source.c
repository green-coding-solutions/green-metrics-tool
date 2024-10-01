#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <sys/time.h>
#include <time.h>
#include "parse_int.h"

// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// TODO: If this code ever gets multi-threaded please review this assumption to
// not pollute another threads state


static long int user_hz;
static unsigned int msleep_time=1000;

static long int read_cpu_cgroup() {

    long int cpu_usage = -1;
    FILE* fd = fopen("/sys/fs/cgroup/cpu.stat", "r"); // check for general readability only once
    int match_result = fscanf(fd, "usage_usec %ld", &cpu_usage);
    if (match_result != 1) {
        fprintf(stderr, "Could not match usage_usec\n");
        exit(1);
    }

    fclose(fd);
    return cpu_usage;
}

static void output_stats() {

    struct timeval now;
    gettimeofday(&now, NULL);

    printf("%ld%06ld %ld\n", now.tv_sec, now.tv_usec, read_cpu_cgroup());
    usleep(msleep_time*1000);
}

static int check_system() {
    const char check_path[] = "/sys/fs/cgroup/cpu.stat";
    FILE* fd = fopen(check_path, "r");

    if (fd == NULL) {
        fprintf(stderr, "Couldn't open cpu.stat file at %s\n", check_path);
        exit(1);
    }
    fclose(fd);
    return 0;
}

int main(int argc, char **argv) {

    int c;
    int check_system_flag = 0;

    setvbuf(stdout, NULL, _IONBF, 0);
    user_hz = sysconf(_SC_CLK_TCK);

    while ((c = getopt (argc, argv, "i:hc")) != -1) {
        switch (c) {
        case 'h':
            printf("Usage: %s [-i msleep_time] [-h]\n\n",argv[0]);
            printf("\t-h      : displays this help\n");
            printf("\t-i      : specifies the milliseconds sleep time that will be slept between measurements\n");
            printf("\t-c      : check system and exit\n\n");

            struct timespec res;
            double resolution;

            printf("\tEnvironment variables:\n");
            printf("\tUserHZ\t\t%ld\n", user_hz);
            clock_getres(CLOCK_REALTIME, &res);
            resolution = res.tv_sec + (((double)res.tv_nsec)/1.0e9);
            printf("\tSystemHZ\t%ld\n", (unsigned long)(1/resolution + 0.5));
            printf("\tCLOCKS_PER_SEC\t%ld\n", CLOCKS_PER_SEC);
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
