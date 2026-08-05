GMT_LIB_DIR = ../../../../../../lib/c
CFLAGS  = -O3 -Wall -Werror -I$(GMT_LIB_DIR) -I/usr/local/cuda-12.9/targets/x86_64-linux/include
LDFLAGS = -L$(GMT_LIB_DIR) -lnvidia-ml -lc

metric-provider-binary: source.c $(GMT_LIB_DIR)/gmt-lib.o $(GMT_LIB_DIR)/gmt-lib.h
	gcc $(CFLAGS) $(GMT_LIB_DIR)/gmt-lib.o $< $(LDFLAGS) -o $@