#include <errno.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/time.h>
#include <ctype.h>
#include <getopt.h>
#include "parse_int.h"

// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// in any case, none of these variables should change between threads
static unsigned int msleep_time=1000;

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

static void output_network_procfs() {
    char buf[200], ifname[20];
    unsigned long long int r_bytes, t_bytes, r_packets, t_packets;
    struct timeval now;

    // instead we could also read from ip -s link, but this might not be as consistent: https://serverfault.com/questions/448768/cat-proc-net-dev-and-ip-s-link-show-different-statistics-which-one-is-lyi
    // The web-link is very old though
    // by testing on our machine though ip link also returned significantly smaller values (~50% less)
    FILE * fd = fopen("/proc/net/dev", "r");
    if ( fd == NULL) {
        fprintf(stderr, "Error - file /proc/net/dev failed to open. Is the container still running? Errno: %d\n", errno);
        exit(1);
    }

    // skip first two lines
    if (fgets(buf, 200, fd) == NULL || fgets(buf, 200, fd) == NULL) {
        fprintf(stderr, "Error or EOF encountered while reading input.\n");
        exit(1);
    }

    int match_result = 0;

    gettimeofday(&now, NULL); // we only make this one time as we believe the overhead of the systemcall is more harmful than the mini time delay for every loop iteration

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

        printf("%ld%06ld %llu %llu %s\n", now.tv_sec, now.tv_usec, r_bytes, t_bytes, trimwhitespace(ifname));
    }

    fclose(fd);

    usleep(msleep_time*1000);
}

static int check_system() {
    const char file_path_proc_net_dev[] = "/proc/net/dev";

    FILE * fd = fopen(file_path_proc_net_dev, "r");
    if (fd == NULL) {
        fprintf(stderr, "Couldn't open /proc/net/dev file\n");
        return 1;
    }

    fclose(fd);

    return 0;
}

int main(int argc, char **argv) {

    int c;
    int check_system_flag = 0;

    setvbuf(stdout, NULL, _IONBF, 0);

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
            printf("\t-c      : check system and exit\n\n");
            exit(0);
        case 'i':
            msleep_time = parse_int(optarg);
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

    while(1) {
        output_network_procfs();
    }

    return 0;
}
