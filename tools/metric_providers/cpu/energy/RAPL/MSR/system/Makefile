CFLAGS = -o3 -Wall -lm -static -static-libgcc

static-binary: source.c
	gcc $< $(CFLAGS) -o $@
	sudo chown root $@
	sudo chmod u+s $@