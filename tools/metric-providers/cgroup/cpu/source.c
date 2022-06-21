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
static char *user_id = "1000"; //TODO: Figure out user_id dynamically, or request

static long int user_hz;

static double read_cpu_proc(FILE *fd) {
    int cpu_usage = -1;
    //char buffer[512];
    //fread(buffer, 512, 1, fd);
    //fscanf(fd, "cpu %*s %*s %*s %s", buffer);

    //printf("Content: %s", buffer);

    fscanf(fd, "cpu %*s %*s %*s %d", &cpu_usage);
    //printf("CPU Usage global: %d", cpu_usage);
    if(cpu_usage>0) {
        return (cpu_usage*1000000)/user_hz;
    }
    else {
        fprintf(stderr, "Error - CPU usage could not be read");
        exit(1);
    }
}


static double read_cpu_cgroup(FILE *fd) {
	double cpu_usage = -1;
	fscanf(fd, "usage_usec %lf", &cpu_usage);
	if(cpu_usage>0) {
		return cpu_usage;
	}
	else {
		fprintf(stderr, "Error - CPU usage could not be read");
		exit(1);
	}
}

double get_cpu_stat(char* filename, int mode) {
	FILE* fd = NULL;
	double result=-1;

	fd = fopen(filename, "r");
	if ( fd == NULL) {
			fprintf(stderr, "Error - file %s failed to open: errno: %d\n", filename, errno);
			exit(1);
	}
    if(mode == 1) {
    	result = read_cpu_cgroup(fd);
    } else {
        result = read_cpu_proc(fd);
    }
	fclose(fd);
	return result;
}

unsigned int interval=1000;
struct container {
	char path[BUFSIZ];
	char *id;
};

int output_stats(struct container *containers, int length) {
	int result = -1;
	
	FILE* cpu_stat_files[length];
	FILE *main_cpu_file;

	double main_cpu_reading_before, main_cpu_reading_after, main_cpu_reading;
	double cpu_readings_before[length];
	double cpu_readings_after[length];
	double container_reading;

	struct timeval now;
	char filename[BUFSIZ];
	int i;


	// Get Energy Readings, set timestamp mark
	gettimeofday(&now, NULL);
	main_cpu_reading_before = get_cpu_stat("/proc/stat", 0);
	for(i=0; i<length; i++) {
		cpu_readings_before[i]=get_cpu_stat(containers[i].path, 1);
	}

	usleep(interval*1000);

	main_cpu_reading_after = get_cpu_stat("/proc/stat", 0);
	for(i=0; i<length; i++) {
		cpu_readings_after[i]=get_cpu_stat(containers[i].path, 1);
	}

	// Display Energy Readings
	// This is in a seperate loop, so that all energy readings are done beforehand as close together as possible	
	for(i=0; i<length; i++) {
		container_reading = cpu_readings_after[i] - cpu_readings_before[i];
		main_cpu_reading = main_cpu_reading_after - main_cpu_reading_before;

        // printf("Main CPU Reading: %f - Container CPU Reading: %f", main_cpu_reading, container_reading);

		double reading;
		if(main_cpu_reading >= 0) {
			if(container_reading == 0 || main_cpu_reading == 0) {
				reading = 0;
			}
			else if(container_reading > 0) {
				reading = container_reading / main_cpu_reading;
			}
			else {
				fprintf(stderr, "Error - container CPU usage negative: %f", container_reading);
				return -1;
			}
		}
		else {
			reading = -1;
			fprintf(stderr, "Error - main CPU reading returning strange data: %f\n", main_cpu_reading);
		}

		printf("%ld%06ld %f %s\n", now.tv_sec, now.tv_usec, reading, containers[i].id);
	}
	return 1;
}

// TODO: better arguement parsing, atm it assumes first argument is interval, 
// 		 and rest are container ids with no real error checking
int main(int argc, char **argv) {
	int c;
	int i;

	struct container containers[argc-2];

	int result=-1;

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