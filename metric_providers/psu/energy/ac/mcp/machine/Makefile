CFLAGS = -o3 -Wall -lm

metric-provider-binary: source.c
	gcc $< $(CFLAGS) -o $@
	sudo chown root $@
	sudo chmod u+s $@