#include <stdio.h>
#include <mach/mach.h>
#include <mach/mach_host.h>
#include <unistd.h>
#include <stdlib.h>
#include <sys/time.h>

static unsigned int msleep_time=1000;


int main(int argc, char **argv) {

    setvbuf(stdout, NULL, _IONBF, 0);

    int c;

    while ((c = getopt (argc, argv, "hi:d")) != -1) {
        switch (c) {
        case 'h':
            printf("Usage: %s [-h] [-m]\n\n",argv[0]);
            printf("\t-h      : displays this help\n");
            printf("\t-i      : specifies the milliseconds sleep time that will be slept between measurements\n\n");
            exit(0);
        case 'i':
            msleep_time = atoi(optarg);
            break;
        default:
            fprintf(stderr,"Unknown option %c\n",c);
            exit(-1);
        }
    }


    host_cpu_load_info_data_t prevCpuLoad;
    host_cpu_load_info_data_t currCpuLoad;
    mach_msg_type_number_t count = HOST_CPU_LOAD_INFO_COUNT;
    kern_return_t status;
    struct timeval now;


    status = host_statistics(mach_host_self(), HOST_CPU_LOAD_INFO, (host_info_t)&prevCpuLoad, &count);
    if (status != KERN_SUCCESS) {
        printf("Failed to retrieve CPU load information\n");
        return 1;
    }

    while (1) {
        status = host_statistics(mach_host_self(), HOST_CPU_LOAD_INFO, (host_info_t)&currCpuLoad, &count);
        if (status != KERN_SUCCESS) {
            printf("Failed to retrieve CPU load information\n");
            return 1;
        }

        natural_t userDiff = currCpuLoad.cpu_ticks[CPU_STATE_USER] - prevCpuLoad.cpu_ticks[CPU_STATE_USER];
        natural_t systemDiff = currCpuLoad.cpu_ticks[CPU_STATE_SYSTEM] - prevCpuLoad.cpu_ticks[CPU_STATE_SYSTEM];
        natural_t idleDiff = currCpuLoad.cpu_ticks[CPU_STATE_IDLE] - prevCpuLoad.cpu_ticks[CPU_STATE_IDLE];
        natural_t niceDiff = currCpuLoad.cpu_ticks[CPU_STATE_NICE] - prevCpuLoad.cpu_ticks[CPU_STATE_NICE];
        unsigned long long computeDiff = userDiff + systemDiff + niceDiff;
        unsigned long long totalDiff = userDiff + systemDiff + idleDiff + niceDiff;

        if (totalDiff > 0) {
            // float userPercent = (userDiff / totalDiff) * 100.0;
            // float systemPercent = (systemDiff / totalDiff) * 100.0;
            // float nicePercent = (niceDiff / totalDiff) * 100.0;
            gettimeofday(&now, NULL); // will set now

            printf("%llu%06llu %llu\n", (unsigned long long)now.tv_sec, (unsigned long long)now.tv_usec, (computeDiff*10000) / totalDiff ); // Deliberate integer conversion. Precision with 0.01% is good enough


            // printf("User CPU utilization: %.2f%%\n", userPercent);
            // printf("System CPU utilization: %.2f%%\n", systemPercent);
            // printf("Nice CPU utilization: %.2f%%\n", nicePercent);
        }

        prevCpuLoad = currCpuLoad;

        usleep(msleep_time*1000);
    }

    return 0;
}
