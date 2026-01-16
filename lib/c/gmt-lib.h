#ifndef GMT_LIB_H
#define GMT_LIB_H

#include <time.h>
#include <sys/time.h>

int check_path(const char* path);
unsigned int parse_int(char *argument);
void get_time_offset(struct timespec *offset);
void get_adjusted_time(struct timeval *adjusted, struct timespec *offset);
bool is_partition_sysfs(const char *devname);

#endif // GMT_LIB_H
