#ifndef GMT_LIB_H
#define GMT_LIB_H

#include <time.h>
#include <sys/time.h>
#include <stdbool.h>

int check_path(const char* path);
unsigned int parse_int(char *argument);
void get_time_offset(struct timespec *offset);
void get_adjusted_time(struct timeval *adjusted, struct timespec *offset);
bool is_partition_sysfs(unsigned int major_number, unsigned int minor_number);

#endif // GMT_LIB_H
