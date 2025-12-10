#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <sys/time.h>
#include <time.h>
#include <string.h> // for strtok
#include <getopt.h>
#include <limits.h>
#include <stdbool.h>
#include "gmt-lib.h"
#include "detect_cgroup_path.h"

// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// in any case, none of these variables should change between threads
static int user_id = -1;
static unsigned int msleep_time=1000;
static struct timespec offset;

static long long int get_memory_cgroup(char* filename) {
    long long int active_file = -1;
    long long int active_anon = -1;
    long long int slab_unreclaimable = -1;
    long long int percpu = -1;
    long long int unevictable = -1;
    long long int totals = 0;
    unsigned long long int value = 0;
    char key[128];

    FILE * fd = fopen(filename, "r");
    if ( fd == NULL) {
        fprintf(stderr, "Error - Could not open path for reading: %s. Maybe the container is not running anymore? Errno: %d\n", filename, errno);
        exit(1);
    }

    while (fscanf(fd, "%127s %llu", key, &value) == 2) {
        if (strcmp(key, "active_anon") == 0) {
            active_anon = value;
            totals += value;
        } else if (strcmp(key, "active_file") == 0) {
            active_file = value;
            totals += value;
        } else if (strcmp(key, "slab_unreclaimable") == 0) {
            slab_unreclaimable = value;
            totals += value;
        } else if (strcmp(key, "percpu") == 0) {
            percpu = value;
            totals += value;
        } else if (strcmp(key, "unevictable") == 0) {
            unevictable = value;
            totals += value;
        }

        if (totals < 0) {
            fprintf(stderr, "Integer overflow in adding memory\n");
            exit(1);
        }

        // finally we do NOT subtract file_mapped as this actually used memory if not
        // deductible via inactive_file
        // in case file_mapped is a shared file it will also show up in shmem
        // sock: this is already part of slab_unreclaimable
    }

    fclose(fd);

    if (active_anon == -1) {
        fprintf(stderr, "Could not match active_anon\n");
        exit(1);
    }

    if (active_file == -1) {
        fprintf(stderr, "Could not match active_file\n");
        exit(1);
    }

    if (slab_unreclaimable == -1) {
        fprintf(stderr, "Could not match slab_unreclaimable\n");
        exit(1);
    }
    if (percpu == -1) {
        fprintf(stderr, "Could not match percpu\n");
        exit(1);
    }
    if (unevictable == -1) {
        fprintf(stderr, "Could not match unevictable\n");
        exit(1);
    }


    return totals;
}

static void output_stats(container_t *containers, int length) {

    struct timeval now;
    int i;

    get_adjusted_time(&now, &offset);

    for(i=0; i<length; i++) {
        printf("%ld%06ld %lld %s\n", now.tv_sec, now.tv_usec, get_memory_cgroup(containers[i].path), containers[i].id);
    }
    usleep(msleep_time*1000);
}

int main(int argc, char **argv) {

    int c;
    bool check_system_flag = false;
    int optarg_len;
    char *containers_string = NULL;  // Dynamic buffer to store optarg
    container_t *containers = NULL;

    setvbuf(stdout, NULL, _IONBF, 0);
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
            printf("\t-s      : string of container IDs or cgroup names separated by comma\n");
            printf("\t-i      : specifies the milliseconds sleep time that will be slept between measurements\n");
            printf("\t-c      : check system and exit\n");
            printf("\n");
            exit(0);
        case 'i':
            msleep_time = parse_int(optarg);
            break;
        case 's':
            optarg_len = strlen(optarg);
            containers_string = (char *)malloc(optarg_len + 1);  // Allocate memory
            if (!containers_string) {
                fprintf(stderr, "Could not allocate memory for containers string\n");
                exit(1);
            }
            memcpy(containers_string, optarg, optarg_len);
            containers_string[optarg_len] = '\0'; // Ensure NUL termination if max length
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
        exit(check_path("/sys/fs/cgroup/memory.stat"));
    }

    get_time_offset(&offset);

    int length = parse_containers("memory.stat", &containers, containers_string, false);

    while(1) {
        output_stats(containers, length);
    }

    free(containers); // since tools is only aborted by CTRL+C this is never called, but memory is freed on program end

    return 0;
}
