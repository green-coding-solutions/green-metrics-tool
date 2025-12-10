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
#include "gmt-lib.h"
#include "gmt-container-lib.h"
#include "detect_cgroup_path.h"

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

static net_io_t get_network_cgroup(unsigned int pid) {
    char buf[200], ifname[20];
    unsigned long long int r_bytes, t_bytes, r_packets, t_packets;
    net_io_t net_io = {0};

    char ns_path[PATH_MAX];
    snprintf(ns_path, PATH_MAX, "/proc/%u/ns/net", pid);

    int fd_ns = open(ns_path, O_RDONLY);   /* Get descriptor for namespace */
    if (fd_ns == -1) {
        fprintf(stderr, "open namespace failed for pid %u", pid);
        exit(1);
    }

    // printf("Entering namespace /proc/%u/ns/net \n", pid);

   if (setns(fd_ns, 0) == -1) { // argument 0 means that any type of NS (IPC, Network, UTS) is allowed
        fprintf(stderr, "setns failed for pid %u", pid);
        exit(1);
    }

    // instead we could also read from ip -s link, but this might not be as consistent: https://serverfault.com/questions/448768/cat-proc-net-dev-and-ip-s-link-show-different-statistics-which-one-is-lyi
    // The web-link is very old though
    // by testing on our machine though ip link also returned significantly smaller values (~50% less)
    FILE * fd = fopen("/proc/net/dev", "r");
    if ( fd == NULL) {
        fprintf(stderr, "Error - file %s failed to open. Is the container still running? Errno: %d\n", "/proc/net/dev", errno);
        exit(1);
    }

    if (fgets(buf, 200, fd) == NULL || fgets(buf, 200, fd) == NULL) {
        fprintf(stderr, "Error or EOF encountered while reading input.\n");
        exit(1);
    }

    int match_result = 0;

    while (fgets(buf, 200, fd)) {
        // We are not counting dropped packets, as we believe they will at least show up in the
        // sender side as not dropped.
        // Since we are iterating over all relevant docker containers we should catch these packets at least in one /proc/net/dev file
        match_result = sscanf(buf, "%[^:]: %llu %llu %*u %*u %*u %*u %*u %*u %llu %llu", ifname, &r_bytes, &r_packets, &t_bytes, &t_packets);
        if (match_result != 5) {
            fprintf(stderr, "Could not match network interface pattern\n");
            exit(1);
        }
        // printf("%s: rbytes: %llu rpackets: %llu tbytes: %llu tpackets: %llu\n", ifname, r_bytes, r_packets, t_bytes, t_packets);
        if (strcmp(trimwhitespace(ifname), "lo") == 0) continue;
        net_io.r_bytes += r_bytes;
        net_io.t_bytes += t_bytes;
    }

    fclose(fd);
    close(fd_ns);

    return net_io;

}

static void output_stats(container_t *containers, int length) {

    struct timeval now;
    int i;

    get_adjusted_time(&now, &offset);

    for(i=0; i<length; i++) {
        net_io_t net_io = get_network_cgroup(containers[i].pid);
        printf("%ld%06ld %llu %llu %s\n", now.tv_sec, now.tv_usec, net_io.r_bytes, net_io.t_bytes, containers[i].id);
    }
    usleep(msleep_time*1000);
}

static int parse_containers(container_t** containers, char* containers_string) {
    if(containers_string == NULL) {
        fprintf(stderr, "Please supply at least one container id or cgroup name with -s XXXX\n");
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
            fclose(fd);
        }
    }

    if(length == 0) {
        fprintf(stderr, "Please supply at least one container id or cgroup name with -s XXXX\n");
        exit(1);
    }
    return length;
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
            printf("\t-s      : string of container IDs or cgroup names separated by comma\n");
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
        check_path("/proc/net/dev");
        exit(check_path("/sys/fs/cgroup/cgroup.procs"));
    }

    get_time_offset(&offset);

    int length = parse_containers("cgroup.procs", &containers, containers_string, true);

    while(1) {
        output_stats(containers, length);
    }

    free(containers); // since tools is only aborted by CTRL+C this is never called, but memory is freed on program end

    return 0;
}
