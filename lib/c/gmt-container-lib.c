#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>


int parse_containers(const char* cgroup_controller, container_t** containers, char* containers_string, bool get_container_pid) {
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

        (*containers)[length-1].path = detect_cgroup_path(cgroup_controller, user_id, id);
        if (get_container_pid) {
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
    }

    if(length == 0) {
        fprintf(stderr, "Please supply at least one container id or cgroup name with -s XXXX\n");
        exit(1);
    }
    return length;
}
