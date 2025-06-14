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
#include <nvml.h>
#include "gmt-lib.h"


// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// in any case, none of these variables should change between threads
static unsigned int msleep_time=1000;
static struct timespec offset;

static void output_stats() {
    struct timeval now;
    nvmlReturn_t result;
    unsigned int device_count;
    nvmlDevice_t device;
    char name[NVML_DEVICE_NAME_BUFFER_SIZE];
//    nvmlUtilization_t utilization;
//    nvmlMemory_t memory;
    unsigned int power_usage;
//    unsigned int power_limit;

    result = nvmlInit();
    if (result != NVML_SUCCESS) {
        fprintf(stderr, "Failed to initialize NVML: %s\n", nvmlErrorString(result));
        exit(1);
    }

    result = nvmlDeviceGetCount(&device_count);
    if (result != NVML_SUCCESS) {
        fprintf(stderr, "Failed to get device count: %s\n", nvmlErrorString(result));
        nvmlShutdown();
        exit(1);
    }

    while (1) {
        get_adjusted_time(&now, &offset);

        for (unsigned int i = 0; i < device_count; i++) {

            nvmlDeviceGetHandleByIndex(i, &device);
            nvmlDeviceGetName(device, name, sizeof(name));
//            printf("GPU %u: %s\n", i, name);

//            nvmlDeviceGetUtilizationRates(device, &utilization);
//            printf("  Utilization: %u%%\n", utilization.gpu);

//            nvmlDeviceGetMemoryInfo(device, &memory);
//            printf("  Memory: %llu MiB / %llu MiB\n", memory.used / 1024 / 1024, memory.total / 1024 / 1024);

//            nvmlDeviceGetEnforcedPowerLimit(device, &power_limit); // mW

            nvmlDeviceGetPowerUsage(device, &power_usage);         // mW
            printf("%ld%06ld %u \"%s-%u\"\n", now.tv_sec, now.tv_usec, power_usage, name, i);

        }
        usleep(msleep_time*1000);
    }


}


static int check_system() {
    nvmlReturn_t result;
    nvmlDevice_t device;
    unsigned int power_usage;
    unsigned int device_count;

    result = nvmlInit();
    if (result != NVML_SUCCESS) {
        fprintf(stderr, "Failed to initialize NVML: %s\n", nvmlErrorString(result));
        return 1;
    }

    result = nvmlDeviceGetCount(&device_count);
    if (result != NVML_SUCCESS) {
        fprintf(stderr, "Failed to get device count: %s\n", nvmlErrorString(result));
        nvmlShutdown();
        exit(1);
    }

    if (device_count <= 0) {
        fprintf(stderr, "No NVIDIA cards found\n");
        nvmlShutdown();
        exit(1);

    }

    nvmlDeviceGetHandleByIndex(0, &device);
    nvmlDeviceGetPowerUsage(device, &power_usage);
    nvmlShutdown();

    return 0;
}

int main(int argc, char **argv) {

    int c;
    bool check_system_flag = false;

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
        exit(check_system());
    }

    get_time_offset(&offset);

    output_stats();

    nvmlShutdown();

    return 0;
}