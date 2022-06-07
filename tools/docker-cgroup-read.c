/*
	TODO: Document what this does
	Compile: gcc -o2 -o docker-read docker-cgroup-read.c 
	Run: ./docker-read [interval] [container1] [container2]... [containerN]
*/

#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <sys/time.h>

static char *user_id = "1000"; //TODO: Figure out user_id dynamically, or request

static double read_cpu(FILE *fd) {
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

double get_cpu_stat(char* filename) {
	FILE* fd = NULL;
	double result=-1;

	fd = fopen(filename, "r+");	// read+ is important! if readonly, cpu stats won't get updated by os :-(
	if ( fd == NULL) {
			fprintf(stderr, "Error - file failed to open: errno: %d\n", errno);
			exit(1);
	}
	result = read_cpu(fd);
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
	main_cpu_reading_before = get_cpu_stat("/sys/fs/cgroup/cpu.stat");
	for(i=0; i<length; i++) {
		cpu_readings_before[i]=get_cpu_stat(containers[i].path);
	}

	usleep(interval*1000);

	main_cpu_reading_after = get_cpu_stat("/sys/fs/cgroup/cpu.stat");
	for(i=0; i<length; i++) {
		cpu_readings_after[i]=get_cpu_stat(containers[i].path);
	}

	// Display Energy Readings
	// This is in a seperate loop, so that all energy readings are done beforehand as close together as possible	
	for(i=0; i<length; i++) {
		container_reading = cpu_readings_after[i] - cpu_readings_before[i];
		main_cpu_reading = main_cpu_reading_after - main_cpu_reading_before;

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
			fprintf(stderr, "Error - main CPU reading returning strange data: %f\n", main_cpu_reading);
			return -1;
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