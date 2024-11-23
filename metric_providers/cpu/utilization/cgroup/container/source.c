#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <sys/time.h>
#include <time.h>
#include <string.h> // for strtok
#include <getopt.h>
#include <limits.h>
#include "parse_int.h"
#include "detect_cgroup_path.h"

#define DOCKER_CONTAINER_ID_BUFFER 65 // Docker container ID size is 64 + 1 byte for NUL termination

typedef struct container_t { // struct is a specification and this static makes no sense here
    char* path;
    char id[DOCKER_CONTAINER_ID_BUFFER];
} container_t;

// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// in any case, none of these variables should change between threads
static int user_id = -1;
static long int user_hz;
static unsigned int msleep_time=1000;

static long int read_cpu_proc(FILE *fd) {
    long int user_time, nice_time, system_time, idle_time, iowait_time, irq_time, softirq_time, steal_time;

    int match_result = fscanf(fd, "cpu %ld %ld %ld %ld %ld %ld %ld %ld", &user_time, &nice_time, &system_time, &idle_time, &iowait_time, &irq_time, &softirq_time, &steal_time);
    if (match_result != 8) {
        fprintf(stderr, "Could not match cpu usage pattern\n");
        exit(1);
    }

    // printf("Read: cpu %ld %ld %ld %ld %ld %ld %ld %ld %ld\n", user_time, nice_time, system_time, idle_time, iowait_time, irq_time, softirq_time, steal_time);
    if(idle_time <= 0) fprintf(stderr, "Idle time strange value %ld \n", idle_time);

    // after this multiplication we are on microseconds
    // integer division is deliberately, cause we don't loose precision as *1000000 is done before
    return ((user_time+nice_time+system_time+idle_time+iowait_time+irq_time+softirq_time+steal_time)*1000000)/user_hz;
}


static long int read_cpu_cgroup(FILE *fd) {
    long int cpu_usage = -1;
    int match_result = fscanf(fd, "usage_usec %ld", &cpu_usage);
    if (match_result != 1) {
        fprintf(stderr, "Could not match usage_sec\n");
        exit(1);
    }
    return cpu_usage;
}

static long int get_cpu_stat(char* filename, int mode) {
    long int result=-1;
    FILE* fd = fopen(filename, "r");

    if ( fd == NULL) {
        fprintf(stderr, "Error - Could not open path for reading: %s. Maybe the container is not running anymore? Errno: %d\n", filename, errno);
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


static void output_stats(container_t* containers, int length) {

    long int main_cpu_reading_before, main_cpu_reading_after, main_cpu_reading;
    long int cpu_readings_before[length];
    long int cpu_readings_after[length];
    long int container_reading;

    struct timeval now;
    int i;

    // Get Energy Readings, set timestamp mark
    gettimeofday(&now, NULL);
    for(i=0; i<length; i++) {
        //printf("Looking at %s ", containers[i].path);
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
                exit(1);
            }
        }
        else {
            fprintf(stderr, "Error - main CPU reading returning strange data: %ld\nBefore: %ld, After %ld", main_cpu_reading, main_cpu_reading_before, main_cpu_reading_after);
            exit(1);
        }

        printf("%ld%06ld %ld %s\n", now.tv_sec, now.tv_usec, reading, containers[i].id);
    }
}

static int parse_containers(container_t** containers, char* containers_string) {
    if(containers_string == NULL) {
        fprintf(stderr, "Please supply at least one container id with -s XXXX\n");
        exit(1);
    }

    *containers = malloc(sizeof(container_t));
    if (!containers) {
        fprintf(stderr, "Could not allocate memory for containers string\n");
        exit(1);
    }
    char *id = strtok(containers_string,",");
    int length = 0;
    FILE* fd = NULL;

    for (; id != NULL; id = strtok(NULL, ",")) {
        //printf("Token: %s\n", id);
        length++;
        *containers = realloc(*containers, length * sizeof(container_t));
        if (!containers) {
            fprintf(stderr, "Could not allocate memory for containers string\n");
            exit(1);
        }
        strncpy((*containers)[length-1].id, id, DOCKER_CONTAINER_ID_BUFFER - 1);
        (*containers)[length-1].id[DOCKER_CONTAINER_ID_BUFFER - 1] = '\0';

        (*containers)[length-1].path = detect_cgroup_path("cpu.stat", user_id, id);
    }

    if(length == 0) {
        fprintf(stderr, "Please supply at least one container id with -s XXXX\n");
        exit(1);
    }

    return length;
}

static int check_system() {
    const char* file_path_cpu_stat;
    const char* file_path_proc_stat;
    int found_error = 0;

    file_path_cpu_stat = "/sys/fs/cgroup/cpu.stat";
    file_path_proc_stat = "/proc/stat";
    
    FILE* fd = fopen(file_path_cpu_stat, "r");
    if (fd == NULL) {
        fprintf(stderr, "Couldn't open cpu.stat file at %s\n", file_path_cpu_stat);
        found_error = 1;
    }

    fd = fopen(file_path_proc_stat, "r");
    if (fd == NULL) {
        fprintf(stderr, "Couldn't open /proc/stat file\n");
        found_error = 1;
    }

    if (fd != NULL) {
        fclose(fd);
    }

    if(found_error) {
        exit(1);
    }

    return 0;
}

int main(int argc, char **argv) {

    int c;
    int check_system_flag = 0;
    char *containers_string = NULL;  // Dynamic buffer to store optarg
    container_t *containers = NULL;

    setvbuf(stdout, NULL, _IONBF, 0);
    user_hz = sysconf(_SC_CLK_TCK);
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
            printf("\t-s      : string of container IDs separated by comma\n");
            printf("\t-i      : specifies the milliseconds sleep time that will be slept between measurements\n\n");
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
        case 's':
            containers_string = (char *)malloc(strlen(optarg) + 1);  // Allocate memory
            if (!containers_string) {
                fprintf(stderr, "Could not allocate memory for containers string\n");
                exit(1);
            }
            strncpy(containers_string, optarg, strlen(optarg));
            containers_string[strlen(optarg)] = '\0'; // Ensure NUL termination if max length
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

    int length = parse_containers(&containers, containers_string);

    while(1) {
        output_stats(containers, length);
    }

    free(containers); // since tools is only aborted by CTRL+C this is never called, but memory is freed on program end

    return 0;
}
