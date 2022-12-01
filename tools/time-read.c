/*
    This file is just present to get the theoretical maximal throughput in terms of
    writes per microsecond.

    Apparently the usleep function has an overhead of 60 usec at least

    Also select() yielded no accuarcy gain, although some voices on the internet
    still say so
*/

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>
#include <sys/time.h>
#include <sys/types.h>


unsigned int interval = 1;
struct timeval before;
struct timeval now;
struct timeval delay;

int main(int argc, char **argv) {
    interval = atoi(argv[1]);
    printf("Interval is %d\n", interval);
    gettimeofday(&before, NULL);
    while (1) {
        gettimeofday(&now, NULL);
        printf("%ld%06ld, usec Difference:, %06ld\n", now.tv_sec, now.tv_usec, now.tv_usec - before.tv_usec);
        before = now;

        // delay.tv_sec =0;
        // delay.tv_usec = interval;//20 ms

        // select(0, NULL,NULL, NULL, &delay);
        interval != 0 && usleep(interval);
        fflush(stdout);
    }
    return 0;
}
