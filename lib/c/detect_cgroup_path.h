#ifndef DETECT_CGROUP_PATH_H
#define DETECT_CGROUP_PATH_H

char* detect_cgroup_path(const char* controller, int user_id, const char* id);

#endif // DETECT_CGROUP_PATH_H