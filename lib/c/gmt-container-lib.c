#include "gmt-container-lib.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <limits.h>
#include <errno.h>
#include <curl/curl.h>


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

char* detect_cgroup_path(const char* controller, int user_id, const char* id) {
    char* path = malloc(PATH_MAX);
    if (path == NULL) {
        fprintf(stderr, "Could not allocate memory for detect_cgroup_path\n");
        exit(1);
    }

    FILE* fd = NULL;

    // Try cgroups v2 with systemd slices (typically in rootless mode)
    snprintf(path, PATH_MAX,
             "/sys/fs/cgroup/user.slice/user-%d.slice/user@%d.service/user.slice/docker-%s.scope/%s",
             user_id, user_id, id, controller);
    fd = fopen(path, "r");
    if (fd != NULL) {
        fclose(fd);
        return path;
    }

    // Try cgroups v2 with systemd but non-slice mountpoints (typically in non-rootless mode)
    snprintf(path, PATH_MAX,
             "/sys/fs/cgroup/system.slice/docker-%s.scope/%s",
             id, controller);
    fd = fopen(path, "r");
    if (fd != NULL) {
        fclose(fd);
        return path;
    }

    // Try cgroups v2 without slice mountpoints (used in Github codespaces)
    snprintf(path, PATH_MAX,
             "/sys/fs/cgroup/docker/%s/%s",
             id, controller);
    fd = fopen(path, "r");
    if (fd != NULL) {
        fclose(fd);
        return path;
    }

    // Try cgroups v2 without slice mountpoints and in subdir (used in Github actions)
    snprintf(path, PATH_MAX,
             "/sys/fs/cgroup/actions_job/%s/%s",
             id, controller);
    fd = fopen(path, "r");
    if (fd != NULL) {
        fclose(fd);
        return path;
    }

    // Try cgroups v2 with session slices (typically for Window Managers)
    snprintf(path, PATH_MAX,
             "/sys/fs/cgroup/user.slice/user-%d.slice/user@%d.service/session.slice/%s/%s",
             user_id, user_id, id, controller);
    fd = fopen(path, "r");
    if (fd != NULL) {
        fclose(fd);
        return path;
    }

    // Try cgroups v2 with user slices (typically for Session applications like gdm)
    snprintf(path, PATH_MAX,
             "/sys/fs/cgroup/user.slice/user-%d.slice/%s/%s",
             user_id, id, controller);
    fd = fopen(path, "r");
    if (fd != NULL) {
        fclose(fd);
        return path;
    }

    // Try cgroups v2 with app slices (typically for user controlled systemd units)
    snprintf(path, PATH_MAX,
             "/sys/fs/cgroup/user.slice/user-%d.slice/user@%d.service/app.slice/%s/%s",
             user_id, user_id, id, controller);
    fd = fopen(path, "r");
    if (fd != NULL) {
        fclose(fd);
        return path;
    }

    // Try cgroups v2 with full cgroup name (typically used for debug purposes)
    snprintf(path, PATH_MAX,
             "/sys/fs/cgroup/%s/%s",
             id, controller);
    fd = fopen(path, "r");
    if (fd != NULL) {
        fclose(fd);
        return path;
    }

    // If no valid path is found, free the allocated memory and error
    free(path);
    fprintf(stderr, "Error - Could not open container for reading: %s. Maybe the container is not running anymore? Errno: %d\n", id, errno);
    exit(1);

}

/*
    Stuff for curl requests to the Docker API
*/

struct string {
    char *ptr;
    size_t len;
};

void init_string(struct string *s) {
    s->len = 0;
    s->ptr = malloc(1);
    s->ptr[0] = '\0';
}

size_t writefunc(void *ptr, size_t size, size_t nmemb, struct string *s) {
    size_t new_len = s->len + size * nmemb;
    s->ptr = realloc(s->ptr, new_len + 1);
    memcpy(s->ptr + s->len, ptr, size * nmemb);
    s->ptr[new_len] = '\0';
    s->len = new_len;
    return size * nmemb;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <container_id>\n", argv[0]);
        return 1;
    }

    const char *container_id = argv[1];

    CURL *curl = curl_easy_init();
    if (!curl) return 1;

    struct string s;
    init_string(&s);

    char url[512];
    snprintf(url, sizeof(url), "http://localhost/containers/%s/json", container_id);

    curl_easy_setopt(curl, CURLOPT_UNIX_SOCKET_PATH, "/var/run/docker.sock");
    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, writefunc);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &s);

    CURLcode res = curl_easy_perform(curl);
    if(res != CURLE_OK) {
        fprintf(stderr, "curl_easy_perform() failed: %s\n", curl_easy_strerror(res));
        return 1;
    }

    // Simple parsing to extract the "Name" field
    char *name_pos = strstr(s.ptr, "\"Name\":\"");
    if (name_pos) {
        name_pos += strlen("\"Name\":\"");
        char *end = strchr(name_pos, '"');
        if (end) {
            *end = '\0';
            printf("Container name: %s\n", name_pos);
            // Remove leading slash if present
            char *clean_name = (*name_pos == '/') ? name_pos + 1 : name_pos;
            char *result = strdup(clean_name); // caller must free
        }
    } else {
        printf("Container name not found\n");
    }

    free(s.ptr);
    curl_easy_cleanup(curl);
    return 0;
}