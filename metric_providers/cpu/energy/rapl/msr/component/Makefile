GMT_LIB_DIR = ../../../../../../lib/c
CFLAGS = -O3 -Wall -Werror -lm -I$(GMT_LIB_DIR)

metric-provider-binary: source.c $(GMT_LIB_DIR)/gmt-lib.o $(GMT_LIB_DIR)/gmt-lib.h
	gcc $(GMT_LIB_DIR)/gmt-lib.o $< $(CFLAGS) -o $@
	sudo chown root:root $@
	sudo chmod u+s $@
