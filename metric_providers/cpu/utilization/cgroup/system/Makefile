LIB_C = ../../../../../lib/c
CFLAGS = -O3 -Wall -Werror -I$(LIB_C)

metric-provider-binary: source.c $(LIB_C)/gmt-lib.o $(LIB_C)/gmt-lib.h $(LIB_C)/detect_cgroup_path.o $(LIB_C)/detect_cgroup_path.h
	gcc $(LIB_C)/gmt-lib.o $(LIB_C)/detect_cgroup_path.o $< $(CFLAGS) -o $@