CFLAGS = -O3 -Wall -Werror -lc -I../../../../../lib/c

metric-provider-binary: source.c ../../../../../lib/c/gmt-lib.o
	gcc ../../../../../lib/c/gmt-lib.o $< $(CFLAGS) -o $@
