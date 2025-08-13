LIB_C = ../../../../../lib/c
CFLAGS = -O3 -Wall -Werror -I$(LIB_C)

metric-provider-binary: source.c $(LIB_C)/gmt-lib.o $(LIB_C)/gmt-lib.h
	gcc $(LIB_C)/gmt-lib.o $< $(CFLAGS) -o $@