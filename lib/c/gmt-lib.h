#ifndef GMT_LIB_H
#define GMT_LIB_H

#include <time.h>
#include <sys/time.h>
#include <stdbool.h>

typedef enum { BLOCK_DEV_DISK, BLOCK_DEV_PARTITION, BLOCK_DEV_HIDDEN } block_dev_type_t;

int check_path(const char* path);
unsigned int parse_int(char *argument);
double parse_double(char *argument);
void get_time_offset(struct timespec *offset);
void get_adjusted_time(struct timeval *adjusted, struct timespec *offset);
block_dev_type_t get_block_device_type_sysfs(unsigned int major_number, unsigned int minor_number);
unsigned int get_min_sleep_time_ms(void);
void validate_min_sleep_time(unsigned int msleep_time, unsigned int min_msleep_time_ms);


#endif // GMT_LIB_H
