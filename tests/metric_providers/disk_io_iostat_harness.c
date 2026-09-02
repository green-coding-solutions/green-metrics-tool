// Test harness around the DiskIoCgroupContainerProvider io.stat parser.
//
// It compiles the provider's own source.c (with its main() renamed out of the
// way) so the parser under test is literally the shipped one, then feeds it
// io.stat content from stdin and prints:
//
//     <rbytes> <wbytes> <torn>
//
// Driven by test_disk_io_iostat.py.

#include <stdio.h>
#include <string.h>

#define main gmt_provider_main_unused
#include "source.c"
#undef main

#define BUF_CAP 65536

int main(void) {
    char buf[BUF_CAP];
    size_t len = fread(buf, 1, BUF_CAP - 1, stdin);
    buf[len] = '\0';

    FILE *fd = fmemopen(buf, len, "r");
    if (fd == NULL) {
        fprintf(stderr, "fmemopen failed\n");
        return 2;
    }

    disk_io_t out = {0};
    bool torn = false;
    parse_io_stat(fd, &out, &torn);
    fclose(fd);

    printf("%llu %llu %d\n", out.rbytes, out.wbytes, torn ? 1 : 0);
    return 0;
}
