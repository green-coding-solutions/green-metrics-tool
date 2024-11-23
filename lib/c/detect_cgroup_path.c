#include "detect_cgroup_path.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <errno.h>

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

    // If no valid path is found, free the allocated memory and error
    free(path);
    fprintf(stderr, "Error - Could not open container for reading: %s. Maybe the container is not running anymore? Errno: %d\n", id, errno);
    exit(1);

}

