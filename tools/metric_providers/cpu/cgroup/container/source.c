#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <sys/time.h>
#include <time.h>
#include <string.h> // for strtok

typedef struct container_t { // struct is a specification and this static makes no sense here
    char path[BUFSIZ];
    char *id;
} container_t;

// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// TODO: If this code ever gets multi-threaded please review this assumption to
// not pollute another threads state
static char *user_id = "1000"; //TODO: Figure out user_id dynamically, or request
static long int user_hz;
static unsigned int msleep_time=1000;
static container_t *containers = NULL;

static long int read_cpu_proc(FILE *fd) {
    long int user_time, nice_time, system_time, idle_time, iowait_time, irq_time, softirq_time, steal_time, guest_time;

    fscanf(fd, "cpu %ld %ld %ld %ld %ld %ld %ld %ld %ld", &user_time, &nice_time, &system_time, &idle_time, &iowait_time, &irq_time, &softirq_time, &steal_time, &guest_time);

    // printf("Read: cpu %ld %ld %ld %ld %ld %ld %ld %ld %ld\n", user_time, nice_time, system_time, idle_time, iowait_time, irq_time, softirq_time, steal_time, guest_time);
    if(idle_time <= 0) fprintf(stderr, "Idle time strange value %ld \n", idle_time);

    // after this multiplication we are on microseconds
    // integer division is deliberately, cause we don't loose precision as *1000000 is done before
    return ((user_time+nice_time+system_time+idle_time+iowait_time+irq_time+softirq_time+steal_time+guest_time)*1000000)/user_hz;
}


static long int read_cpu_cgroup(FILE *fd) {
    long int cpu_usage = -1;
    fscanf(fd, "usage_usec %ld", &cpu_usage);
    return cpu_usage;
}

static long int get_cpu_stat(char* filename, int mode) {
    FILE* fd = NULL;
    long int result=-1;

    fd = fopen(filename, "r");
    if ( fd == NULL) {
            fprintf(stderr, "Error - file %s failed to open: errno: %d\n", filename, errno);
            exit(1);
    }
    if(mode == 1) {
        result = read_cpu_cgroup(fd);
        // printf("Got cgroup: %ld", result);
    } else {
        result = read_cpu_proc(fd);
        // printf("Got /proc/stat: %ld", result);
    }
    fclose(fd);
    return result;
}


static int output_stats(container_t *containers, int length) {

    long int main_cpu_reading_before, main_cpu_reading_after, main_cpu_reading;
    long int cpu_readings_before[length];
    long int cpu_readings_after[length];
    long int container_reading;

    struct timeval now;
    int i;


    // Get Energy Readings, set timestamp mark
    gettimeofday(&now, NULL);
    for(i=0; i<length; i++) {
        cpu_readings_before[i]=get_cpu_stat(containers[i].path, 1);
    }
    main_cpu_reading_before = get_cpu_stat("/proc/stat", 0);

    usleep(msleep_time*1000);

    for(i=0; i<length; i++) {
        cpu_readings_after[i]=get_cpu_stat(containers[i].path, 1);
    }
    main_cpu_reading_after = get_cpu_stat("/proc/stat", 0);

    // Display Energy Readings
    // This is in a seperate loop, so that all energy readings are done beforehand as close together as possible
    for(i=0; i<length; i++) {
        container_reading = cpu_readings_after[i] - cpu_readings_before[i];
        main_cpu_reading = main_cpu_reading_after - main_cpu_reading_before;

        // printf("Main CPU Reading: %ld - Container CPU Reading: %ld\n", main_cpu_reading, container_reading);

        long int reading;
        if(main_cpu_reading >= 0) {
            if(container_reading == 0 || main_cpu_reading == 0) {
                reading = 0;
            }
            else if(container_reading > 0) {
                reading = (container_reading*10000) / main_cpu_reading; // Deliberate integer conversion. Precision with 0.01% is good enough
            }
            else {
                fprintf(stderr, "Error - container CPU usage negative: %ld", container_reading);
                return -1;
            }
        }
        else {
            reading = -1;
            fprintf(stderr, "Error - main CPU reading returning strange data: %ld\nBefore: %ld, After %ld", main_cpu_reading, main_cpu_reading_before, main_cpu_reading_after);
        }

        printf("%ld%06ld %ld %s\n", now.tv_sec, now.tv_usec, reading, containers[i].id);
    }
    return 1;
}

// TODO: better arguement parsing, atm it assumes first argument is msleep_time,
//       and rest are container ids with no real error checking
int main(int argc, char **argv) {

    int c;
    int length = 0;

    setvbuf(stdout, NULL, _IONBF, 0);
    user_hz = sysconf(_SC_CLK_TCK);

    while ((c = getopt (argc, argv, "i:s:h")) != -1) {
        switch (c) {
        case 'h':
            printf("Usage: %s [-i msleep_time] [-h]\n\n",argv[0]);
            printf("\t-h      : displays this help\n");
            printf("\t-s      : string of container IDs separated by comma\n");
            printf("\t-i      : specifies the milliseconds sleep time that will be slept between measurements\n\n");

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
            msleep_time = atoi(optarg);
            break;
        case 's':
            containers = malloc(sizeof(container_t));
            char *id = strtok(optarg,",");
            for (; id != NULL; id = strtok(NULL, ",")) {
                //printf("Token: %s\n", id);
                length++;
                containers = realloc(containers, length * sizeof(container_t));
                containers[length-1].id = id;
                sprintf(containers[length-1].path,
                    "/sys/fs/cgroup/user.slice/user-%s.slice/user@%s.service/user.slice/docker-%s.scope/cpu.stat",
                    user_id, user_id, id);

                FILE* fd = NULL;
                fd = fopen(containers[length-1].path, "r"); // check for general readability only once
                if ( fd == NULL) {
                        fprintf(stderr, "Error - file %s failed to open: errno: %d\n", containers[length-1].path, errno);
                        exit(1);
                }
                fclose(fd);
            }

            break;
        default:
            fprintf(stderr,"Unknown option %c\n",c);
            exit(-1);
        }
    }

    if(containers == NULL) {
        printf("Please supply at least one container id with -s XXXX\n");
        exit(1);
    }

    while(1) {
        output_stats(containers, length);
    }

    free(containers); // since tools is only aborted by CTRL+C this is never called, but memory is freed on program end

    return 0;
}
