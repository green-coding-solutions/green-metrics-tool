CFLAGS = -O3 -Wall -I../../../../../lib/c

metric-provider-binary: source.c
	gcc ../../../../../lib/c/parse_int.o ../../../../../lib/c/detect_cgroup_path.o $< $(CFLAGS) -o $@
