#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/sysctl.h>
#include <sys/time.h>
#include <mach/mach.h>
#include <mach/mach_host.h>
#include <unistd.h>

void loop_utilization(unsigned int msleep_time) {
    processor_info_array_t cpuInfo = NULL, prevCpuInfo = NULL;
    mach_msg_type_number_t numCpuInfo, numPrevCpuInfo;

    while(1){
        natural_t numCPUsU = 0U;
        kern_return_t err = host_processor_info(mach_host_self(), PROCESSOR_CPU_LOAD_INFO, &numCPUsU, &cpuInfo, &numCpuInfo);

        if (err == KERN_SUCCESS) {

            float ut_total = 0U;
            struct timeval now;

            for (unsigned i = 0; i < numCPUsU; ++i) {
                float inUse, total;
                if (prevCpuInfo) {
                    inUse = ((cpuInfo[(CPU_STATE_MAX * i) + CPU_STATE_USER] - prevCpuInfo[(CPU_STATE_MAX * i) + CPU_STATE_USER]) +
                            (cpuInfo[(CPU_STATE_MAX * i) + CPU_STATE_SYSTEM] - prevCpuInfo[(CPU_STATE_MAX * i) + CPU_STATE_SYSTEM]) +
                            (cpuInfo[(CPU_STATE_MAX * i) + CPU_STATE_NICE] - prevCpuInfo[(CPU_STATE_MAX * i) + CPU_STATE_NICE]));
                    total = inUse + (cpuInfo[(CPU_STATE_MAX * i) + CPU_STATE_IDLE] - prevCpuInfo[(CPU_STATE_MAX * i) + CPU_STATE_IDLE]);
                } else {
                    inUse = cpuInfo[(CPU_STATE_MAX * i) + CPU_STATE_USER] + cpuInfo[(CPU_STATE_MAX * i) + CPU_STATE_SYSTEM] + cpuInfo[(CPU_STATE_MAX * i) + CPU_STATE_NICE];
                    total = inUse + cpuInfo[(CPU_STATE_MAX * i) + CPU_STATE_IDLE];
                }
                ut_total = ut_total + (inUse / total);
            }

            gettimeofday(&now, NULL);
            printf("%ld%06i %i\n", now.tv_sec, now.tv_usec, (int)(ut_total * 100 / numCPUsU));

            if (prevCpuInfo) {
                size_t prevCpuInfoSize = sizeof(integer_t) * numPrevCpuInfo;
                vm_deallocate(mach_task_self(), (vm_address_t)prevCpuInfo, prevCpuInfoSize);
            }

            prevCpuInfo = cpuInfo;
            numPrevCpuInfo = numCpuInfo;

            cpuInfo = NULL;
            numCpuInfo = 0U;
        } else {
            fprintf(stderr, "Error: %s\n", mach_error_string(err));
        }

    usleep(msleep_time*1000);
    }
}


static int check_system() {
    processor_info_array_t cpuInfo = NULL;
    mach_msg_type_number_t numCpuInfo;
    natural_t numCPUsU = 0U;

    kern_return_t err = host_processor_info(mach_host_self(), PROCESSOR_CPU_LOAD_INFO, &numCPUsU, &cpuInfo, &numCpuInfo);

    if (err == KERN_SUCCESS) {
        if (numCPUsU > 0){
            return 0;
        }else{
            fprintf(stderr, "The call was successful but the data is wrong.");
            return 1;
        }
    }else{
        fprintf(stderr, "There was an error getting CPU info: %s\n", mach_error_string(err));
        return err;
    }
}

int main(int argc, char **argv) {

    int c;
    unsigned int msleep_time=1000;

    setvbuf(stdout, NULL, _IONBF, 0);

    while ((c = getopt (argc, argv, "i:hc")) != -1) {
        switch (c) {
        case 'h':
            printf("Usage: %s [-i msleep_time] [-h]\n\n",argv[0]);
            printf("\t-h      : displays this help\n");
            printf("\t-i      : specifies the milliseconds sleep time that will be slept between measurements\n");
            printf("\t-c      : check system and exit\n\n");
            exit(0);
        case 'i':
            msleep_time = atoi(optarg);
            if (msleep_time < 50){
                fprintf(stderr,"A value of %i is to small. Results will include 0s as the kernel does not update as fast.\n",msleep_time);
            }
            break;
        case 'c':
            exit(check_system());
        default:
            fprintf(stderr,"Unknown option %c\n",c);
            exit(-1);
        }
    }

    loop_utilization(msleep_time);

    return 0;
}
