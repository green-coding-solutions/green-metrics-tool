CFLAGS = -O3 -Wall -Werror -I../../../../../lib/c

metric-provider-binary: source.c
	gcc ../../../../../lib/c/gmt-lib.o ../../../../../lib/c/detect_cgroup_path.o $< $(CFLAGS) -o $@