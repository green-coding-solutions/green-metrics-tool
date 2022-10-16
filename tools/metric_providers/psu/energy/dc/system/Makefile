CFLAGS = -o3 -Wall -lm -static-libgcc -L/opt/picoscope/lib -I/opt/picoscope/include -lpicohrdl -lc -DDEBUG_BUILD

static-binary: source.c
	gcc $< $(CFLAGS) -o $@