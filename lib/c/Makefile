CFLAGS = -O3 -Wall

all: parse_int.o detect_cgroup_path.o

parse_int.o: parse_int.c
	gcc -c $< $(CFLAGS) -o $@

detect_cgroup_path.o: detect_cgroup_path.c
	gcc -c $< $(CFLAGS) -o $@