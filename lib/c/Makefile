CFLAGS = -O3 -Wall

all: gmt-lib.o detect_cgroup_path.o

gmt-lib.o: gmt-lib.c
	gcc -c $< $(CFLAGS) -o $@

detect_cgroup_path.o: detect_cgroup_path.c
	gcc -c $< $(CFLAGS) -o $@