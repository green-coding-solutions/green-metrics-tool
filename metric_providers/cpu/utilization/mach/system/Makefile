GMT_LIB_DIR = ../../../../../lib/c
CFLAGS = -O3 -Wall -Werror -I$(GMT_LIB_DIR)

metric-provider-binary: source.c $(GMT_LIB_DIR)/gmt-lib.o $(GMT_LIB_DIR)/gmt-lib.h
	gcc $(GMT_LIB_DIR)/gmt-lib.o $< $(CFLAGS) -o $@