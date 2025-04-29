CFLAGS  = -O3 -Wall -Werror -I../../../../../../lib/c
LDFLAGS = -L../../../../../../lib/c -lnvidia-ml -lc

metric-provider-binary: source.c
	gcc $(CFLAGS) ../../../../../../lib/c/gmt-lib.o $< $(LDFLAGS) -o $@