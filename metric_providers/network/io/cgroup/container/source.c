#define _GNU_SOURCE // important, cause otherwise setns is undefined
#include <errno.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h> // for strtok
#include <fcntl.h>
#include <unistd.h>
#include <sys/time.h>
#include <time.h>
#include <ctype.h>
#include <getopt.h>
#include <limits.h>
#include <stdbool.h>
#include <sys/types.h>
#include <sys/stat.h>
#include "gmt-lib.h"
#include "detect_cgroup_path.h"

#define DOCKER_CONTAINER_ID_BUFFER 65 // Docker container ID size is 64 + 1 byte for NUL termination

typedef struct container_t { // struct is a specification and this static makes no sense here
    char* path;
    char ns_path[PATH_MAX];
    char id[DOCKER_CONTAINER_ID_BUFFER];
    unsigned int pid;
} container_t;

typedef struct net_io_t {
    unsigned long long int r_bytes;
    unsigned long long int t_bytes;
} net_io_t;

// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// in any case, none of these variables should change between threads
static int user_id = -1;
static unsigned int msleep_time=1000;
static struct timespec offset;

static char *trimwhitespace(char *str) {
  char *end;

  // Trim leading space
  while(isspace((unsigned char)*str)) str++;

  if(*str == 0)  // All spaces?
    return str;

  // Trim trailing space
  end = str + strlen(str) - 1;
  while(end > str && isspace((unsigned char)*end)) end--;

  // Write new null terminator character
  end[1] = '\0';

  return str;
}

static void output_stats(container_t *containers, int length) {
    struct timeval now;
    static ino_t last_ns_ino = 0;
    static int fd_ns = -1;
    struct stat ns_stat;
    FILE *fd = NULL;
    char buf[200], ifname[20];
    unsigned long long int r_bytes, t_bytes, r_packets, t_packets;

    get_adjusted_time(&now, &offset);

    for (int i = 0; i < length; i++) {
        if (stat(containers[i].ns_path, &ns_stat) == -1) {
            fprintf(stderr, "Failed to stat namespace for pid %u\n", containers[i].pid);
            exit(1);
        }

        // If namespace has changed, reopen and setns
        if (last_ns_ino != ns_stat.st_ino) {

            fd_ns = open(containers[i].ns_path, O_RDONLY);
            if (fd_ns == -1) {
                fprintf(stderr, "Failed to open namespace for pid %u\n", containers[i].pid);
                exit(1);
            }

            if (setns(fd_ns, 0) == -1) {
                fprintf(stderr, "setns failed for pid %u\n", containers[i].pid);
                exit(1);
            }

            last_ns_ino = ns_stat.st_ino;
            // Read network I/O from /proc/net/dev
            fd = fopen("/proc/net/dev", "r"); // reopen different file

             if (!fd) {
                fprintf(stderr, "Failed to open /proc/net/dev. Is the container still running?\n");
                exit(1);
            }

        }

        fseek(fd, 0, SEEK_SET);

        net_io_t net_io = {0};

        if (fgets(buf, 200, fd) == NULL || fgets(buf, 200, fd) == NULL) {
            fprintf(stderr, "Error or EOF encountered while reading input.\n");
            exit(1);
        }

        while (fgets(buf, sizeof(buf), fd)) {
            if (sscanf(buf, "%[^:]: %llu %llu %*u %*u %*u %*u %*u %*u %llu %llu",
                       ifname, &r_bytes, &r_packets, &t_bytes, &t_packets) != 5) {
                fprintf(stderr, "Could not parse /proc/net/dev line.\n");
                exit(1);
            }

            if (strcmp(trimwhitespace(ifname), "lo") == 0)
                continue;

            net_io.r_bytes += r_bytes;
            net_io.t_bytes += t_bytes;
        }



        printf("%ld%06ld %llu %llu %s\n", now.tv_sec, now.tv_usec, net_io.r_bytes, net_io.t_bytes, containers[i].id);
    }

    usleep(msleep_time * 1000);
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

        (*containers)[length-1].path = detect_cgroup_path("cgroup.procs", user_id, id);
        FILE* fd = fopen((*containers)[length-1].path, "r");
        if (fd != NULL) {
            int match_result = fscanf(fd, "%u", &(*containers)[length-1].pid);
            if (match_result != 1) {
                fprintf(stderr, "Could not match container PID\n");
                exit(1);
            }

            snprintf((*containers)[length-1].ns_path, PATH_MAX, "/proc/%u/ns/net", (*containers)[length-1].pid);

            fclose(fd);
        }
    }

    if(length == 0) {
        fprintf(stderr, "Please supply at least one container id with -s XXXX\n");
        exit(1);
    }
    return length;
}

static int check_system() {
    const char* file_path_cgroup_procs;
    const char file_path_proc_net_dev[] = "/proc/net/dev";
    int found_error = 0;

    file_path_cgroup_procs = "/sys/fs/cgroup/cgroup.procs";
    FILE* fd = fopen(file_path_cgroup_procs, "r");
    if (fd == NULL) {
        fprintf(stderr, "Couldn't open cgroup.procs file at %s\n", file_path_cgroup_procs);
        found_error = 1;
    }

    fd = fopen(file_path_proc_net_dev, "r");
    if (fd == NULL) {
        fprintf(stderr, "Couldn't open /proc/net/dev file\n");
        found_error = 1;
    }

    if (fd != NULL) {
        fclose(fd);
    }

    if(found_error) {
        exit(1);
    }

    return 0;
}

int main(int argc, char **argv) {

    int c;
    bool check_system_flag = false;
    int optarg_len;
    char *containers_string = NULL;  // Dynamic buffer to store optarg
    container_t *containers = NULL;

    setvbuf(stdout, NULL, _IONBF, 0);
    user_id = getuid(); // because the file is run without sudo but has the suid bit set we only need getuid and not geteuid

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
        exit(check_system());
    }

    get_time_offset(&offset);

    int length = parse_containers(&containers, containers_string);

    while(1) {
        output_stats(containers, length);
    }

    free(containers); // since tools is only aborted by CTRL+C this is never called, but memory is freed on program end

    return 0;
}
