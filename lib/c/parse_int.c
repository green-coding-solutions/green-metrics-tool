#include "parse_int.h"

#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <limits.h>

unsigned int parse_int(char *argument) {
    unsigned long int number = 0;
    char *endptr;

    errno = 0;  // Reset errno before the call
    number = strtoul(argument, &endptr, 10);

    if (errno == ERANGE && (number == LONG_MAX || number == LONG_MIN)) {
        fprintf(stderr, "Error: Could not parse -i argument - Number out of range\n");
        exit(1);
    } else if (errno != 0 && number == 0) {
        fprintf(stderr, "Error: Could not parse -i argument - Invalid number\n");
        exit(1);
    } else if (endptr == argument) {
        fprintf(stderr, "Error: Could not parse -i argument - No digits were found\n");
        exit(1);
    } else if (*endptr != '\0') {
        fprintf(stderr, "Error: Could not parse -i argument - Invalid characters after number\n");
        exit(1);
    }

    return number;
}

