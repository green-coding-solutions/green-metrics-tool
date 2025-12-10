GMT_LIB_DIR = ../../../../../lib/c
CFLAGS = -O3 -Wall -Werror -lc -I$(GMT_LIB_DIR)

metric-provider-binary: source.c $(GMT_LIB_DIR)/gmt-lib.o $(GMT_LIB_DIR)/gmt-lib.h $(GMT_LIB_DIR)/gmt-container-lib.o $(GMT_LIB_DIR)/gmt-container-lib.h $(GMT_LIB_DIR)/detect_cgroup_path.o $(GMT_LIB_DIR)/detect_cgroup_path.h
	gcc $(GMT_LIB_DIR)/gmt-lib.o $(GMT_LIB_DIR)/gmt-container-lib.o $(GMT_LIB_DIR)/detect_cgroup_path.o $< $(CFLAGS) -o $@
	sudo chown root $@
	sudo chmod u+s $@