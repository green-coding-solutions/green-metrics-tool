CFLAGS  = -O3 -Wall -Werror -I../../../../../../lib/c -I/usr/local/cuda-12.9/targets/x86_64-linux/include
LDFLAGS = -L../../../../../../lib/c -lnvidia-ml -lc

metric-provider-binary: source.c
	gcc $(CFLAGS) ../../../../../../lib/c/gmt-lib.o $< $(LDFLAGS) -o $@