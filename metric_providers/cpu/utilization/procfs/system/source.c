#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <sys/time.h>
#include <time.h>
#include <stdbool.h>
#include "gmt-lib.h"

typedef struct procfs_time_t { // struct is a specification and this static makes no sense here
    unsigned long user_time;
    unsigned long nice_time;
    unsigned long system_time;
    unsigned long idle_time;
    unsigned long iowait_time;
    unsigned long irq_time;
    unsigned long softirq_time;
    // technically here is also steal_time, guest_time, guest_nice time
    // but these values are not compatible with old systems (to be fair: < linux 2.6)
    // but they are zero in our non-virtualized setups anyway
    // and if you are in a virtualized environment we make the case, that this is not time we see as the utilization of the looked at system. It happended outside
    // gmt reporters are to capture the work done. Not all time executed somewhere out of scope


    unsigned long compute_time; // custom attr by us not in standard /proc/stat format
    unsigned long non_compute_time; // custom attr by us not in standard /proc/stat format
} procfs_time_t;


// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// TODO: If this code ever gets multi-threaded please review this assumption to
// not pollute another threads state
static unsigned int msleep_time=1000;
static struct timespec offset;

static void read_cpu_proc(procfs_time_t* procfs_time_struct) {

    FILE* fd = fopen("/proc/stat", "r");
    if ( fd == NULL) {
        fprintf(stderr, "Error - file %s failed to open: errno: %d\n", "/proc/stat/", errno);
        exit(1);
    }

    // see explanation above in procfs_time_struct why we do not caputure steal_time etc.
    int match_result = fscanf(fd, "cpu %ld %ld %ld %ld %ld %ld %ld", &procfs_time_struct->user_time, &procfs_time_struct->nice_time, &procfs_time_struct->system_time, &procfs_time_struct->idle_time, &procfs_time_struct->iowait_time, &procfs_time_struct->irq_time, &procfs_time_struct->softirq_time);
    if (match_result != 7) {
        fprintf(stderr, "Could not match cpu usage pattern\n");
        exit(1);
    }

    // debug
    // printf("Read: cpu %ld %ld %ld %ld %ld %ld %ld %ld %ld\n", procfs_time_struct->user_time, procfs_time_struct->nice_time, procfs_time_struct->system_time, procfs_time_struct->idle_time, procfs_time_struct->iowait_time, procfs_time_struct->irq_time, procfs_time_struct->softirq_time);

    fclose(fd);

    procfs_time_struct->non_compute_time = procfs_time_struct->idle_time + procfs_time_struct->iowait_time + procfs_time_struct->irq_time + procfs_time_struct->softirq_time;
    // in /proc/stat nice time is NOT included in the user time! (it is in cgroups however though)
    procfs_time_struct->compute_time = procfs_time_struct->user_time + procfs_time_struct->system_time + procfs_time_struct->nice_time;
}


static void output_stats() {

    long int  non_compute_reading, compute_time_reading;
    procfs_time_t main_cpu_reading_before;
    procfs_time_t main_cpu_reading_after;
    struct timeval now;

    get_adjusted_time(&now, &offset);

    read_cpu_proc(&main_cpu_reading_before); // will set main_cpu_reading_before

    usleep(msleep_time*1000);

    read_cpu_proc(&main_cpu_reading_after); // will set main_cpu_reading_before

    non_compute_reading = main_cpu_reading_after.non_compute_time - main_cpu_reading_before.non_compute_time;
    compute_time_reading = main_cpu_reading_after.compute_time - main_cpu_reading_before.compute_time;

    // debug
    // printf("Main CPU Idle Reading: %ld\nMain CPU Compute Time Reading: %ld\n", idle_reading, compute_time_reading);
    // printf("%ld%06ld %f\n", now.tv_sec, now.tv_usec, (double)compute_time_reading / (double)(compute_time_reading+idle_reading));

    // main output to Stdout
    printf("%ld%06ld %ld\n", now.tv_sec, now.tv_usec, (compute_time_reading*10000) / (compute_time_reading+non_compute_reading) ); // Deliberate integer conversion. Precision with 0.01% is good enough
}

static int check_system() {
    const char check_path[] = "/proc/stat";

    FILE* fd = fopen(check_path, "r");

    if (fd == NULL) {
        fprintf(stderr, "Couldn't open %s file\n", check_path);
        exit(1);
    }
    fclose(fd);
    return 0;
}

int main(int argc, char **argv) {

    int c;
    bool check_system_flag = false;

    setvbuf(stdout, NULL, _IONBF, 0);

    while ((c = getopt (argc, argv, "i:hc")) != -1) {
        switch (c) {
        case 'h':
            printf("Usage: %s [-i msleep_time] [-h]\n\n",argv[0]);
            printf("\t-h      : displays this help\n");
            printf("\t-i      : specifies the milliseconds sleep time that will be slept between measurements\n");
            printf("\t-c      : check system and exit\n");
            printf("\n");

            struct timespec res;
            double resolution;

            printf("\tEnvironment variables:\n");
            clock_getres(CLOCK_REALTIME, &res);
            resolution = res.tv_sec + (((double)res.tv_nsec)/1.0e9);
            printf("\tSystemHZ\t%ld\n", (unsigned long)(1/resolution + 0.5));
            printf("\tCLOCKS_PER_SEC\t%ld\n", CLOCKS_PER_SEC);
            exit(0);
        case 'i':
            msleep_time = parse_int(optarg);
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
        exit(check_system());
    }

    get_time_offset(&offset);

    while(1) {
        output_stats();
    }

    return 0;
}
