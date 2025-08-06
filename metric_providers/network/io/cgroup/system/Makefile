CFLAGS = -O3 -Wall -Werror -lc -I../../../../../lib/c

metric-provider-binary: source.c ../../../../../lib/c/gmt-lib.o ../../../../../lib/c/gmt-lib.h ../../../../../lib/c/detect_cgroup_path.o ../../../../../lib/c/detect_cgroup_path.h
	gcc ../../../../../lib/c/gmt-lib.o ../../../../../lib/c/detect_cgroup_path.o $< $(CFLAGS) -o $@
	sudo chown root $@
	sudo chmod u+s $@