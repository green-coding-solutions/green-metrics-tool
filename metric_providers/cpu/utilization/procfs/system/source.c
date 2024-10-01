#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <sys/time.h>
#include <time.h>
#include "parse_int.h"

typedef struct procfs_time_t { // struct is a specification and this static makes no sense here
    unsigned long user_time;
    unsigned long nice_time;
    unsigned long system_time;
    unsigned long wait_time;
    unsigned long iowait_time;
    unsigned long irq_time;
    unsigned long softirq_time;
    unsigned long steal_time;
    // guest times are ignored as they are already accounted in user_time, system_time
    unsigned long compute_time; // custom attr by us not in standard /proc/stat format
    unsigned long idle_time; // custom attr by us not in standard /proc/stat format
} procfs_time_t;


// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// TODO: If this code ever gets multi-threaded please review this assumption to
// not pollute another threads state
static unsigned int msleep_time=1000;

static void read_cpu_proc(procfs_time_t* procfs_time_struct) {

    FILE* fd = fopen("/proc/stat", "r");
    if ( fd == NULL) {
        fprintf(stderr, "Error - file %s failed to open: errno: %d\n", "/proc/stat/", errno);
        exit(1);
    }

    int match_result = fscanf(fd, "cpu %ld %ld %ld %ld %ld %ld %ld %ld", &procfs_time_struct->user_time, &procfs_time_struct->nice_time, &procfs_time_struct->system_time, &procfs_time_struct->wait_time, &procfs_time_struct->iowait_time, &procfs_time_struct->irq_time, &procfs_time_struct->softirq_time, &procfs_time_struct->steal_time);
    if (match_result != 8) {
        fprintf(stderr, "Could not match cpu usage pattern\n");
        exit(1);
    }

    // debug
    // printf("Read: cpu %ld %ld %ld %ld %ld %ld %ld %ld %ld\n", procfs_time_struct->user_time, procfs_time_struct->nice_time, procfs_time_struct->system_time, procfs_time_struct->idle_time, procfs_time_struct->iowait_time, procfs_time_struct->irq_time, procfs_time_struct->softirq_time, procfs_time_struct->steal_time);

    fclose(fd);

    // after this multiplication we are on microseconds
    // integer division is deliberately, cause we don't loose precision as *1000000 is done before

    procfs_time_struct->idle_time = procfs_time_struct->wait_time + procfs_time_struct->iowait_time;
    procfs_time_struct->compute_time = procfs_time_struct->user_time + procfs_time_struct->nice_time + procfs_time_struct->system_time + procfs_time_struct->irq_time + procfs_time_struct->softirq_time + procfs_time_struct->steal_time;
}


static void output_stats() {

    long int  idle_reading, compute_time_reading;
    procfs_time_t main_cpu_reading_before;
    procfs_time_t main_cpu_reading_after;
    struct timeval now;

    gettimeofday(&now, NULL); // will set now
    read_cpu_proc(&main_cpu_reading_before); // will set main_cpu_reading_before

    usleep(msleep_time*1000);

    read_cpu_proc(&main_cpu_reading_after); // will set main_cpu_reading_before

    idle_reading = main_cpu_reading_after.idle_time - main_cpu_reading_before.idle_time;
    compute_time_reading = main_cpu_reading_after.compute_time - main_cpu_reading_before.compute_time;

    // debug
    // printf("Main CPU Idle Reading: %ld\nMain CPU Compute Time Reading: %ld\n", idle_reading, compute_time_reading);
    // printf("%ld%06ld %f\n", now.tv_sec, now.tv_usec, (double)compute_time_reading / (double)(compute_time_reading+idle_reading));

    // main output to Stdout
    printf("%ld%06ld %ld\n", now.tv_sec, now.tv_usec, (compute_time_reading*10000) / (compute_time_reading+idle_reading) ); // Deliberate integer conversion. Precision with 0.01% is good enough
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
    int check_system_flag = 0;

    setvbuf(stdout, NULL, _IONBF, 0);

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
