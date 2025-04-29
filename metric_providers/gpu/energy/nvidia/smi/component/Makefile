CFLAGS = -O3 -Wall -Werror -lc -I../../../../../../lib/c -lnvidia-ml

metric-provider-binary: source.c
	gcc ../../../../../../lib/c/gmt-lib.o $< $(CFLAGS) -o $@