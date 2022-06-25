/*
    TODO: Document what this does
    Compile: gcc -o3 -o docker-read docker-cgroup-read.c -static -static-libgcc
    Run: ./docker-read [interval] [container1] [container2]... [containerN]
*/

#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <sys/time.h>
#include <time.h>


// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// TODO: If this code ever gets multi-threaded please review this assumption to
// not pollute another threads state


static char *user_id = "1000"; //TODO: Figure out user_id dynamically, or request
static long int user_hz;
static unsigned int interval=1000;
static struct container {
    char path[BUFSIZ];
    char *id;
};

static long int read_cpu_proc(FILE *fd) {
    long int user_time, nice_time, system_time, idle_time, iowait_time, irq_time, softirq_time, steal_time, guest_time;

    fscanf(fd, "cpu %ld %ld %ld %ld %ld %ld %ld %ld %ld", &user_time, &nice_time, &system_time, &idle_time, &iowait_time, &irq_time, &softirq_time, &steal_time, &guest_time);

    // printf("Read: cpu %ld %ld %ld %ld %ld %ld %ld %ld %ld\n", user_time, nice_time, system_time, idle_time, iowait_time, irq_time, softirq_time, steal_time, guest_time);
    if(idle_time <= 0) fprintf(stderr, "Idle time strange value %ld \n", idle_time);

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


static int output_stats(struct container *containers, int length) {

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

    usleep(interval*1000);

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

        double reading;
        if(main_cpu_reading >= 0) {
            if(container_reading == 0 || main_cpu_reading == 0) {
                reading = 0;
            }
            else if(container_reading > 0) {
                reading = (double) container_reading / (double) main_cpu_reading;
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

        printf("%ld%06ld %f %s\n", now.tv_sec, now.tv_usec, reading, containers[i].id);
    }
    return 1;
}

// TODO: better arguement parsing, atm it assumes first argument is interval,
//       and rest are container ids with no real error checking
int main(int argc, char **argv) {
    int i;

    struct container containers[argc-2];

    int result=-1; // for status value of output_stats. therefore int not long

    setvbuf(stdout, NULL, _IONBF, 0);

    user_hz = sysconf(_SC_CLK_TCK);
    if(argc>=3) {
        interval = atoi(argv[1]);
        for (i = 2; i < argc && i < BUFSIZ; i++) {
            containers[i-2].id = argv[i];
            sprintf(containers[i-2].path,
                "/sys/fs/cgroup/user.slice/user-%s.slice/user@%s.service/user.slice/docker-%s.scope/cpu.stat",
                user_id, user_id, argv[i]);
        }
    }
    else {
        struct timespec res;
        double resolution;

        printf("UserHZ   %ld\n", user_hz);

        clock_getres(CLOCK_REALTIME, &res);
        resolution = res.tv_sec + (((double)res.tv_nsec)/1.0e9);

        printf("SystemHZ %ld\n", (unsigned long)(1/resolution + 0.5));

        printf("CLOCKS_PER_SEC %ld\n", CLOCKS_PER_SEC);

        fprintf(stderr, "Please provide at least two arguements - one interval (in milliseconds), and at least one container id.\n");
        return -1;
    }

    if(interval>0) {
        result = 0;
        while(1 && result != -1) {
            result = output_stats(containers, argc-2);
        }
    }

    if (result<0) {
        fprintf(stderr, "Something has gone wrong.\n");
        return -1;
    }

    return 0;
}
