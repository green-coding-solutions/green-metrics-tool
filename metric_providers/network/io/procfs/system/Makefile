CFLAGS = -O3 -Wall -Werror -lc -I../../../../../lib/c

metric-provider-binary: source.c ../../../../../lib/c/gmt-lib.o ../../../../../lib/c/gmt-lib.h
	gcc ../../../../../lib/c/gmt-lib.o $< $(CFLAGS) -o $@
