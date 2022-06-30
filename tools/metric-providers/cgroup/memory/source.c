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

// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// TODO: If this code ever gets multi-threaded please review this assumption to
// not pollute another threads state

static const char *user_id = "1000"; //TODO: Figure out user_id dynamically, or request
static unsigned int interval=1000;
static struct container {
    char path[BUFSIZ];
    char *id;
};


static long int get_memory_cgroup(char* filename) {
	long int memory = -1;

    FILE * fd = fopen(filename, "r");
    if ( fd == NULL) {
            fprintf(stderr, "Error - file %s failed to open: errno: %d\n", filename, errno);
            exit(1);
    }

	fscanf(fd, "%ld", &memory);
	if(memory>0) {
        fclose(fd);
		return memory;
	}
	else {
		fprintf(stderr, "Error - memory.current could not be read");
        fclose(fd);
		exit(1);
	}

}

static int output_stats(struct container *containers, int length) {
	
	struct timeval now;
	int i;

    gettimeofday(&now, NULL);
    for(i=0; i<length; i++) {
        printf("%ld%06ld %ld %s\n", now.tv_sec, now.tv_usec, get_memory_cgroup(containers[i].path), containers[i].id);
    }

	return 1;
}

int main(int argc, char **argv) {
	int i;

	struct container containers[argc-2];

	setvbuf(stdout, NULL, _IONBF, 0);

	if(argc>=3) {
		interval = atoi(argv[1]);
		for (i = 2; i < argc && i < BUFSIZ; i++) {
	    	containers[i-2].id = argv[i];
	    	sprintf(containers[i-2].path,
	    		"/sys/fs/cgroup/user.slice/user-%s.slice/user@%s.service/user.slice/docker-%s.scope/memory.current",
	    		user_id, user_id, argv[i]);
	    }
	}
	else {

		fprintf(stderr, "Please provide at least two arguements - one interval (in milliseconds), and at least one container id.\n");
		return -1;
	}

	if(interval>0) {
		while(1) {
			output_stats(containers, argc-2);
            usleep(interval*1000);
		}
	}

	return 0;
}
