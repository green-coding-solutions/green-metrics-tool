CFLAGS = -o3 -Wall -lc

static-binary: source.c
	gcc $< $(CFLAGS) -o $@
	sudo chown root $@
	sudo chmod u+s $@