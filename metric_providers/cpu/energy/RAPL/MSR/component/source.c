/* Read the RAPL registers on recent (>sandybridge) Intel processors    */
/*                                    */
/* There are currently three ways to do this:                */
/*    1. Read the MSRs directly with /dev/cpu/??/msr            */
/*    2. Use the perf_event_open() interface                */
/*    3. Read the values from the sysfs powercap interface        */
/*                                    */
/* MSR Code originally based on a (never made it upstream) linux-kernel    */
/*    RAPL driver by Zhang Rui <rui.zhang@intel.com>            */
/*    https://lkml.org/lkml/2011/5/26/93                */
/* Additional contributions by:                        */
/*    Romain Dolbeau -- romain @ dolbeau.org                */
/*                                    */
/* For raw MSR access the /dev/cpu/??/msr driver must be enabled and    */
/*    permissions set to allow read access.                */
/*    You might need to "modprobe msr" before it will work.        */
/*                                    */
/* perf_event_open() support requires at least Linux 3.14 and to have    */
/*    /proc/sys/kernel/perf_event_paranoid < 1            */
/*                                    */
/* the sysfs powercap interface got into the kernel in             */
/*    2d281d8196e38dd (3.13)                        */
/*                                    */
/* Vince Weaver -- vincent.weaver @ maine.edu -- 11 September 2015    */
/*                                    */

#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <errno.h>
#include <inttypes.h>
#include <unistd.h>
#include <math.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/time.h>


/* AMD Support */
#define MSR_AMD_RAPL_POWER_UNIT            0xc0010299

#define MSR_AMD_PKG_ENERGY_STATUS        0xc001029B
#define MSR_AMD_PP0_ENERGY_STATUS        0xc001029A

/* Intel support */

#define MSR_INTEL_RAPL_POWER_UNIT        0x606
/*
 * Platform specific RAPL Domains.
 * Note that PP1 RAPL Domain is supported on 062A only
 * And DRAM RAPL Domain is supported on 062D only
 */
/* Package RAPL Domain */
#define MSR_PKG_RAPL_POWER_LIMIT    0x610
#define MSR_INTEL_PKG_ENERGY_STATUS    0x611
#define MSR_PKG_PERF_STATUS        0x613
#define MSR_PKG_POWER_INFO        0x614

/* PP0 RAPL Domain */
#define MSR_PP0_POWER_LIMIT        0x638
#define MSR_INTEL_PP0_ENERGY_STATUS    0x639
#define MSR_PP0_POLICY            0x63A
#define MSR_PP0_PERF_STATUS        0x63B

/* PP1 RAPL Domain, may reflect to uncore devices */
#define MSR_PP1_POWER_LIMIT        0x640
#define MSR_PP1_ENERGY_STATUS        0x641
#define MSR_PP1_POLICY            0x642

/* DRAM RAPL Domain */
#define MSR_DRAM_POWER_LIMIT        0x618
#define MSR_DRAM_ENERGY_STATUS        0x619
#define MSR_DRAM_PERF_STATUS        0x61B
#define MSR_DRAM_POWER_INFO        0x61C

/* PSYS RAPL Domain */
#define MSR_PLATFORM_ENERGY_STATUS    0x64d

/* RAPL UNIT BITMASK */
#define POWER_UNIT_OFFSET    0
#define POWER_UNIT_MASK        0x0F

#define ENERGY_UNIT_OFFSET    0x08
#define ENERGY_UNIT_MASK    0x1F00

#define TIME_UNIT_OFFSET    0x10
#define TIME_UNIT_MASK        0xF000


static int open_msr(int core) {

    char msr_filename[BUFSIZ];
    int fd;

    sprintf(msr_filename, "/dev/cpu/%d/msr", core);
    fd = open(msr_filename, O_RDONLY);
    if ( fd < 0 ) {
        if ( errno == ENXIO ) {
            fprintf(stderr, "rdmsr: No CPU %d\n", core);
            exit(2);
        } else if ( errno == EIO ) {
            fprintf(stderr, "rdmsr: CPU %d doesn't support MSRs\n",
                    core);
            exit(3);
        } else {
            perror("rdmsr:open");
            exit(127);
        }
    }

    return fd;
}

static long long read_msr(int fd, unsigned int which) {

    uint64_t data;

    if ( pread(fd, &data, sizeof data, which) != sizeof data ) {
        perror("rdmsr:pread");
        fprintf(stderr,"Error reading MSR %x\n",which);
        exit(127);
    }

    return (long long)data;
}

#define CPU_VENDOR_INTEL    1
#define CPU_VENDOR_AMD        2

#define CPU_SANDYBRIDGE        42
#define CPU_SANDYBRIDGE_EP    45
#define CPU_IVYBRIDGE        58
#define CPU_IVYBRIDGE_EP    62
#define CPU_HASWELL        60
#define CPU_HASWELL_ULT        69
#define CPU_HASWELL_GT3E    70
#define CPU_HASWELL_EP        63
#define CPU_BROADWELL        61
#define CPU_BROADWELL_GT3E    71
#define CPU_BROADWELL_EP    79
#define CPU_BROADWELL_DE    86
#define CPU_SKYLAKE        78
#define CPU_SKYLAKE_HS        94
#define CPU_SKYLAKE_X        85
#define CPU_KNIGHTS_LANDING    87
#define CPU_KNIGHTS_MILL    133
#define CPU_KABYLAKE_MOBILE    142
#define CPU_KABYLAKE        158
#define CPU_ATOM_SILVERMONT    55
#define CPU_ATOM_AIRMONT    76
#define CPU_ATOM_MERRIFIELD    74
#define CPU_ATOM_MOOREFIELD    90
#define CPU_ATOM_GOLDMONT    92
#define CPU_ATOM_GEMINI_LAKE    122
#define CPU_ATOM_DENVERTON    95
#define CPU_TIGER_LAKE        140

#define CPU_AMD_FAM17H        0xc000


// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// TODO: If this code ever gets multi-threaded please review this assumption to
// not pollute another threads state
static unsigned int msr_rapl_units,msr_pkg_energy_status,msr_pp0_energy_status;
static unsigned int msleep_time=1000;

static int detect_cpu(void) {

    FILE *fff;

    int vendor=-1,family,model=-1;
    char buffer[BUFSIZ],*result;
    char vendor_string[BUFSIZ];

    fff=fopen("/proc/cpuinfo","r");
    if (fff==NULL) return -1;

    while(1) {
        result=fgets(buffer,BUFSIZ,fff);
        if (result==NULL) break;

        if (!strncmp(result,"vendor_id",8)) {
            sscanf(result,"%*s%*s%s",vendor_string);

            if (!strncmp(vendor_string,"GenuineIntel",12)) {
                vendor=CPU_VENDOR_INTEL;
            }
            if (!strncmp(vendor_string,"AuthenticAMD",12)) {
                vendor=CPU_VENDOR_AMD;
            }
        }

        if (!strncmp(result,"cpu family",10)) {
            sscanf(result,"%*s%*s%*s%d",&family);
        }

        if (!strncmp(result,"model",5)) {
            sscanf(result,"%*s%*s%d",&model);
        }

    }

    if (vendor==CPU_VENDOR_INTEL) {
        if (family!=6) {
            fprintf(stderr, "Wrong CPU family %d\n",family);
            return -1;
        }

        msr_rapl_units=MSR_INTEL_RAPL_POWER_UNIT;
        msr_pkg_energy_status=MSR_INTEL_PKG_ENERGY_STATUS;
        msr_pp0_energy_status=MSR_INTEL_PP0_ENERGY_STATUS;
    }

    if (vendor==CPU_VENDOR_AMD) {

        msr_rapl_units=MSR_AMD_RAPL_POWER_UNIT;
        msr_pkg_energy_status=MSR_AMD_PKG_ENERGY_STATUS;
        msr_pp0_energy_status=MSR_AMD_PP0_ENERGY_STATUS;

        if (family!=23) {
            fprintf(stderr, "Wrong CPU family %d\n",family);
            return -1;
        }
        model=CPU_AMD_FAM17H;
    }

    fclose(fff);

    return model;
}


#define MAX_CPUS    1024
#define MAX_PACKAGES    16

static int total_cores=0,total_packages=0;
static int package_map[MAX_PACKAGES];

static int detect_packages(void) {

    char filename[BUFSIZ];
    FILE *fff;
    int package;
    int i;

    for(i=0;i<MAX_PACKAGES;i++) package_map[i]=-1;

    for(i=0;i<MAX_CPUS;i++) {
        sprintf(filename,"/sys/devices/system/cpu/cpu%d/topology/physical_package_id",i);
        fff=fopen(filename,"r");
        if (fff==NULL) break;
        fscanf(fff,"%d",&package);
        fclose(fff);

        if (package_map[package]==-1) {
            total_packages++;
            package_map[package]=i;
        }

    }

    total_cores=i;
    return 0;
}

#define MEASURE_ENERGY_PKG 1
#define MEASURE_DRAM 2

int dram_avail=0;
int different_units=0;
double cpu_energy_units[MAX_PACKAGES],dram_energy_units[MAX_PACKAGES];
unsigned int energy_status;
double energy_units[MAX_PACKAGES];

static int check_availability(int cpu_model, int measurement_mode) {

    if(measurement_mode == MEASURE_DRAM){
        switch(cpu_model) {
            case CPU_SANDYBRIDGE_EP:
            case CPU_IVYBRIDGE_EP:
                dram_avail=1;
                different_units=0;
                break;

            case CPU_HASWELL_EP:
            case CPU_BROADWELL_EP:
            case CPU_SKYLAKE_X:
                dram_avail=1;
                different_units=1;
                break;

            case CPU_KNIGHTS_LANDING:
            case CPU_KNIGHTS_MILL:
                dram_avail=1;
                different_units=1;
                break;

            case CPU_SANDYBRIDGE:
            case CPU_IVYBRIDGE:
                dram_avail=0;
                different_units=0;
                break;

            case CPU_HASWELL:
            case CPU_HASWELL_ULT:
            case CPU_HASWELL_GT3E:
            case CPU_BROADWELL:
            case CPU_BROADWELL_GT3E:
            case CPU_ATOM_GOLDMONT:
            case CPU_ATOM_GEMINI_LAKE:
            case CPU_ATOM_DENVERTON:
                dram_avail=1;
                different_units=0;
                break;

            case CPU_SKYLAKE:
            case CPU_SKYLAKE_HS:
            case CPU_KABYLAKE:
            case CPU_KABYLAKE_MOBILE:
                dram_avail=1;
                different_units=0;
                break;

            case CPU_AMD_FAM17H:
                dram_avail=0;
                different_units=0;
                break;
            case CPU_TIGER_LAKE:
                dram_avail=0;        // guess, find documentation
                different_units=0;   // guess, find documentation
                break;
        }
    }

    if(measurement_mode == MEASURE_DRAM && !dram_avail) {
        fprintf(stderr,"DRAM not available for your processer.\n");
        exit(-1);
    }

    if (cpu_model<0) {
        fprintf(stderr, "\tUnsupported CPU model %d\n",cpu_model);
        exit(-1);
    }


    return 0;
}

static int setup_measurement_units(int measurement_mode) {
    int fd;
    int j;
    long long result;
    for(j=0;j<total_packages;j++) {
        fd=open_msr(package_map[j]);

        /* Calculate the units used */
        result=read_msr(fd,msr_rapl_units);

        // as per specifications, power unit MSR has the following information in the following bits:
        // 0-3 -> power units
        // 8-12 -> energy status units
        // 16-19 -> time units
        // 4-7, 13-15, and 20-63 are all reserved bits

        //power_units and time_units are not actually used... should we be using them?
        //power_units=pow(0.5,(double)(result&0xf)); //multiplying by 0xf will give you the first 4 bits
        //time_units=pow(0.5,(double)((result>>16)&0xf));

        cpu_energy_units[j]=pow(0.5,(double)((result>>8)&0x1f)); //multiplying by 0x1f will give you the first 5 bits

        if(measurement_mode == MEASURE_DRAM && different_units) {
            dram_energy_units[j]=pow(0.5,(double)16);
        }
        else if (measurement_mode == MEASURE_DRAM && !different_units) {
            dram_energy_units[j]=cpu_energy_units[j];
        }
        close(fd);
    }

    for(j=0;j<total_packages;j++) {
        if(measurement_mode == MEASURE_ENERGY_PKG)
        {
            energy_status = msr_pkg_energy_status;
            energy_units[j] = cpu_energy_units[j];
        }
        else if(measurement_mode == MEASURE_DRAM) {
            energy_status = MSR_DRAM_ENERGY_STATUS;
            energy_units[j] = dram_energy_units[j];
        }
        else {
            fprintf(stderr,"Unknown measurement mode: %d\n",measurement_mode);
            exit(-1);
        }
    }
    return 0;
}

static int check_system() {
    int fd = open_msr(0);
    if (fd < 0) {
        fprintf(stderr, "Couldn't open MSR 0\n");
        exit(127);
    }
    long long msr_data = read_msr(fd, energy_status);

    if(msr_data <= 0) {
        fprintf(stderr, "rapl MSR had 0 or negative values: %lld\n", msr_data);
        exit(127);
    }
    close(fd);
    return 0;

}

static int rapl_msr() {
    int fd;
    long long result;
    double package_before[MAX_PACKAGES],package_after[MAX_PACKAGES];
    int j;
    struct timeval now;

    for(j=0;j<total_packages;j++) {

        fd=open_msr(package_map[j]);
        /* Package Energy */

        result=read_msr(fd,energy_status);
        /*
        if(result<0){
            fprintf(stderr,"Negative Energy Reading: %lld\n", result);
            exit(-1);
        }*/
        package_before[j]=(double)result*energy_units[j];
        close(fd);
    }

    usleep(msleep_time*1000);

    for(j=0;j<total_packages;j++) {
        fd=open_msr(package_map[j]);

        double energy_output = 0.0;
        result=read_msr(fd,energy_status);

        // As we are reading the MSR as an unsigned int, so the reading should never be negative
        // However, in case it does somehow, we still don't want it to abort
        /*
        if(result<0){
            fprintf(stderr,"Negative Energy Reading: %lld\n", result);
            exit(-1);
        }*/
        package_after[j]=(double)result*energy_units[j];
        energy_output = package_after[j]-package_before[j];

        // The register can overflow at some point, leading to the subtraction giving an incorrect value (negative)
        // For now, skip reporting this value. in the future, we can use a branchless alternative
        if(energy_output>=0) {
            gettimeofday(&now, NULL);
            printf("%ld%06ld %ld Package_%d\n", now.tv_sec, now.tv_usec, (long int)(energy_output*1000), j);
        }
        /*
        else {
            fprintf(stderr, "Energy reading had unexpected value: %f", energy_output);
            exit(-1);
        }*/

        close(fd);
    }

    return 0;
}

int main(int argc, char **argv) {

    int c;
    int cpu_model;
    int measure_mode = MEASURE_ENERGY_PKG;
    int check_system_flag = 0;

    while ((c = getopt (argc, argv, "hi:dc")) != -1) {
        switch (c) {
        case 'h':
            printf("Usage: %s [-h] [-m]\n\n",argv[0]);
            printf("\t-h      : displays this help\n");
            printf("\t-i      : specifies the milliseconds sleep time that will be slept between measurements\n");
            printf("\t-d      : measure the dram energy instead of the entire package\n");
            printf("\t-c      : check system and exit\n");
            exit(0);
        case 'i':
            msleep_time = atoi(optarg);
            break;
        case 'd':
            measure_mode=MEASURE_DRAM;
            break;
        case 'c':
            check_system_flag = 1;
            break;
        default:
            fprintf(stderr,"Unknown option %c\n",c);
            exit(-1);
        }
    }


    setvbuf(stdout, NULL, _IONBF, 0);

    cpu_model=detect_cpu();
    detect_packages();
    check_availability(cpu_model, measure_mode);
    setup_measurement_units(measure_mode);

    if(check_system_flag){
        exit(check_system()); 
    }

    while(1) {
        rapl_msr();
    }

    return 0;
}
