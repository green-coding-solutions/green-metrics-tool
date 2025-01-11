CFLAGS = -O3 -Wall -lc -I../../../../../lib/c

metric-provider-binary: source.c
	gcc ../../../../../lib/c/parse_int.o ../../../../../lib/c/detect_cgroup_path.o $< $(CFLAGS) -o $@
	sudo chown root $@
	sudo chmod u+s $@