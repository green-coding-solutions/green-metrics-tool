CFLAGS = -o3 -Wall -lm -static-libgcc -L./ -lpicohrdl -lc

static-binary: source.c
	gcc $< $(CFLAGS) -o $@