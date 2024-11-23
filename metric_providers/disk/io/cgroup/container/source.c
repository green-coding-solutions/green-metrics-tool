#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <sys/time.h>
#include <string.h> // for strtok
#include <getopt.h>
#include <limits.h>
#include "parse_int.h"
#include "detect_cgroup_path.h"


#define DOCKER_CONTAINER_ID_BUFFER 65 // Docker container ID size is 64 + 1 byte for NUL termination

typedef struct container_t { // struct is a specification and this static makes no sense here
    char* path;
    char id[DOCKER_CONTAINER_ID_BUFFER];
} container_t;

typedef struct disk_io_t { // struct is a specification and this static makes no sense here
    unsigned long long int rbytes;
    unsigned long long int wbytes;
} disk_io_t;


// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// in any case, none of these variables should change between threads
static int user_id = -1;
static unsigned int msleep_time=1000;

static disk_io_t get_disk_cgroup(char* filename) {
    long long int rbytes = -1;
    long long int wbytes = -1;
    disk_io_t disk_io = {0};

    FILE * fd = fopen(filename, "r");
    if ( fd == NULL) {
        fprintf(stderr, "Error - Could not open path for reading: %s. Maybe the container is not running anymore? Errno: %d\n", filename, errno);
        exit(1);
    }

    while (fscanf(fd, "%*u:%*u rbytes=%lld wbytes=%lld rios=%*u wios=%*u dbytes=%*u dios=%*u", &rbytes, &wbytes) == 2) {
        disk_io.rbytes += rbytes;
        disk_io.wbytes += wbytes;
    }

    fclose(fd);

    if(rbytes < 0 || wbytes < 0) {
        fprintf(stderr, "Error - io.stat could not be read or was < 0.");
        exit(1);
    }

    return disk_io;
}

static void output_stats(container_t *containers, int length) {

    struct timeval now;
    int i;

    gettimeofday(&now, NULL);
    for(i=0; i<length; i++) {
        disk_io_t disk_io = get_disk_cgroup(containers[i].path);
        printf("%ld%06ld %llu %llu %s\n", now.tv_sec, now.tv_usec, disk_io.rbytes, disk_io.wbytes, containers[i].id);
    }
    usleep(msleep_time*1000);
}

static int parse_containers(container_t** containers, char* containers_string) {
    if(containers_string == NULL) {
        fprintf(stderr, "Please supply at least one container id with -s XXXX\n");
        exit(1);
    }

    *containers = malloc(sizeof(container_t));
    if (!containers) {
        fprintf(stderr, "Could not allocate memory for containers string\n");
        exit(1);
    }
    char *id = strtok(containers_string,",");
    int length = 0;

    for (; id != NULL; id = strtok(NULL, ",")) {
        //printf("Token: %s\n", id);
        length++;
        *containers = realloc(*containers, length * sizeof(container_t));
        if (!containers) {
            fprintf(stderr, "Could not allocate memory for containers string\n");
            exit(1);
        }

        strncpy((*containers)[length-1].id, id, DOCKER_CONTAINER_ID_BUFFER - 1);
        (*containers)[length-1].id[DOCKER_CONTAINER_ID_BUFFER - 1] = '\0';

        (*containers)[length-1].path = detect_cgroup_path("io.stat", user_id, id);
    }

    if(length == 0) {
        fprintf(stderr, "Please supply at least one container id with -s XXXX\n");
        exit(1);
    }
    return length;
}

static int check_system() {
    const char* check_path;

    check_path = "/sys/fs/cgroup/io.stat";

    FILE* fd = fopen(check_path, "r");

    if (fd == NULL) {
        fprintf(stderr, "Couldn't open io.stat file at %s\n", check_path);
        exit(1);
    }
    fclose(fd);
    return 0;
}

int main(int argc, char **argv) {

    int c;
    int check_system_flag = 0;
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
            printf("\t-s      : string of container IDs separated by comma\n");
            printf("\t-i      : specifies the milliseconds sleep time that will be slept between measurements\n");
            printf("\t-c      : check system and exit\n\n");
            exit(0);
        case 'i':
            msleep_time = parse_int(optarg);
            break;
        case 's':
            containers_string = (char *)malloc(strlen(optarg) + 1);  // Allocate memory
            if (!containers_string) {
                fprintf(stderr, "Could not allocate memory for containers string\n");
                exit(1);
            }
            strncpy(containers_string, optarg, strlen(optarg));
            containers_string[strlen(optarg)] = '\0'; // Ensure NUL termination if max length
            break;
        case 'c':
            check_system_flag = 1;
            break;
        default:
            fprintf(stderr,"Unknown option %c\n",c);
            exit(-1);
        }
    }

    if(check_system_flag){
        exit(check_system());
    }

    int length = parse_containers(&containers, containers_string);

    while(1) {
        output_stats(containers, length);
    }

    free(containers); // since tools is only aborted by CTRL+C this is never called, but memory is freed on program end

    return 0;
}
