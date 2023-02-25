CFLAGS = -o3 -Wall -lc

metric-provider-binary: source.c
	gcc $< $(CFLAGS) -o $@
	sudo chown root $@
	sudo chmod u+s $@