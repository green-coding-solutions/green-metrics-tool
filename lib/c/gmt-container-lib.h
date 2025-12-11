#ifndef CONTAINER_H
#define CONTAINER_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <curl/curl.h>

#define DOCKER_CONTAINER_ID_BUFFER 65 // Docker container ID size is 64 + 1 byte for NUL termination

// response string for curl
struct string {
    char *ptr;
    size_t len;
};

typedef struct container_t {
    char *path;
    char *name;
    char id[DOCKER_CONTAINER_ID_BUFFER];
    unsigned int pid; // will be empty in many usages as only network currently needs it
} container_t;

// parse the containers from the -s XXXX string
int parse_containers(const char* cgroup_controller, int user_id, container_t** containers, char* containers_string, bool get_container_pid);

// find cgroup path in various location in /sys/fs
char* detect_cgroup_path(const char* controller, int user_id, container_t container);

// Initialize string struct
void init_string(struct string *s);

// Callback for libcurl to write response data
size_t writefunc(void *ptr, size_t size, size_t nmemb, struct string *s);

// Function to get container name from container ID
char* get_container_name(const char *container_id);

#endif // CONTAINER_H