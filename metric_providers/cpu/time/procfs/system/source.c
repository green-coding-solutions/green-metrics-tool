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

static long int read_cpu_proc() {
    long int user_time, nice_time, system_time, idle_time, iowait_time, irq_time, softirq_time, steal_time;
    FILE* fd = fopen("/proc/stat", "r");

    int match_result = fscanf(fd, "cpu %ld %ld %ld %ld %ld %ld %ld %ld", &user_time, &nice_time, &system_time, &idle_time, &iowait_time, &irq_time, &softirq_time, &steal_time);
    if (match_result != 8) {
        fprintf(stderr, "Could not match cpu usage pattern\n");
        exit(1);
    }

    // printf("Read: cpu %ld %ld %ld %ld %ld %ld %ld %ld %ld\n", user_time, nice_time, system_time, idle_time, iowait_time, irq_time, softirq_time, steal_time);
    if(idle_time <= 0) fprintf(stderr, "Idle time strange value %ld \n", idle_time);

    fclose(fd);

    // after this multiplication we are on microseconds
    // integer division is deliberately, cause we don't loose precision as *1000000 is done before
    return ((user_time+nice_time+system_time+idle_time+iowait_time+irq_time+softirq_time+steal_time)*1000000)/user_hz;
}

static void output_stats() {

    struct timeval now;

    gettimeofday(&now, NULL);
    printf("%ld%06ld %ld\n", now.tv_sec, now.tv_usec, read_cpu_proc());
    usleep(msleep_time*1000);
}

static int check_system() {
    const char check_path[] = "/proc/stat";
    
    FILE* fd = fopen(check_path, "r");

    if (fd == NULL) {
        fprintf(stderr, "Couldn't open /proc/stat file\n");
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
