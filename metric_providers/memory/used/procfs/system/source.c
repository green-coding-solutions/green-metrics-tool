#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <sys/time.h>
#include <time.h>
#include <getopt.h>
#include <string.h>
#include <ctype.h>
#include <stdbool.h>
#include "gmt-lib.h"

// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// in any case, none of these variables should change between threads
static unsigned int msleep_time=1000;
static struct timespec offset;

// just a helper function
void print_repr(const char *str) {
    while (*str) {
        if (*str == '\n') {
            printf("\\n");
        } else if (*str == '\t') {
            printf("\\t");
        } else if (*str == '\r') {
            printf("\\r");
        } else if (*str == '\\') {
            printf("\\\\");
        } else if (isprint((unsigned char)*str)) {
            putchar(*str);  // Print printable characters as-is
        } else {
            // Print non-printable characters as hex
            printf("\\x%02x", (unsigned char)*str);
        }
        str++;
    }
    printf("\n");
}

static long long int get_memory_procfs() {

    long long int active = -1;
    long long int slab_unreclaimable = -1;
    long long int percpu = -1;
    long long int unevictable = -1;
    long long int totals = 0;
    unsigned long long int value = 0;
    char key[128];

    FILE * fd = fopen("/proc/meminfo", "r");
    if ( fd == NULL) {
        fprintf(stderr, "Error - Could not open /proc/meminfo for reading\n");
        exit(1);
    }

    while (fscanf(fd, "%127[^:]:%*[ \t]%llu kB\n", key, &value) == 2) {
        //printf("%s\n", key);
        //print_repr(key); // for debugging
        if (strcmp(key, "Active") == 0) { // contains anon and file equivalent to cgroups
            active = value;
            totals += value;
        } else if (strcmp(key, "SUnreclaim") == 0) {
            slab_unreclaimable = value;
            totals += value;
        } else if (strcmp(key, "Percpu") == 0) {
            percpu = value;
            totals += value;
        } else if (strcmp(key, "Unevictable") == 0) {
            unevictable = value;
            totals += value;
        }

        if (totals < 0) {
            fprintf(stderr, "Integer overflow in adding memory\n");
            exit(1);
        }

        // we DO NOT subtract shmem as we do in the cgroups, as in the OS we want to account for it
        // we further deduct inactive_* as this can be freed to be compatbile with how
        // we caclulate for the cgroup reporter
        // inactive does not have to be subtracted, as it already is not present
    }

    fclose(fd);

    if (active == -1) {
        fprintf(stderr, "Could not match active\n");
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

    // note that here we need to use 1024 instead of 1000 as we are already coming from kiB and not kB
    totals = totals * 1024; // outputted value is in Bytes then

    return totals;

}

static void output_stats() {
    struct timeval now;
    get_adjusted_time(&now, &offset);

    printf("%ld%06ld %lld\n", now.tv_sec, now.tv_usec, get_memory_procfs());
    usleep(msleep_time*1000);

}


int main(int argc, char **argv) {

    int c;
    bool check_system_flag = false;

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
            printf("\t-c      : check system and exit\n");
            printf("\n");
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
        exit(check_path("/proc/meminfo"));
    }

    get_time_offset(&offset);

    while(1) {
        output_stats();
    }

    return 0;
}
