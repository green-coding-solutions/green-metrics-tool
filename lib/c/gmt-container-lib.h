#ifndef CONTAINER_H
#define CONTAINER_H

#define DOCKER_CONTAINER_ID_BUFFER 65 // Docker container ID size is 64 + 1 byte for NUL termination

typedef struct container_t {
    char *path;
    char name[512];
    char id[DOCKER_CONTAINER_ID_BUFFER];
    unsigned int pid; // will be empty in many usages as only network currently needs it
} container_t;

int parse_containers(const char* cgroup_controller, container_t** containers, char* containers_string, bool get_container_pid);

#endif // CONTAINER_H