LIB_C = ../../../../../../lib/c
CFLAGS  = -O3 -Wall -Werror -I$(LIB_C) -I/usr/local/cuda-12.9/targets/x86_64-linux/include
LDFLAGS = -L$(LIB_C) -lnvidia-ml -lc

metric-provider-binary: source.c $(LIB_C)/gmt-lib.o $(LIB_C)/gmt-lib.h
	gcc $(CFLAGS) $(LIB_C)/gmt-lib.o $< $(LDFLAGS) -o $@