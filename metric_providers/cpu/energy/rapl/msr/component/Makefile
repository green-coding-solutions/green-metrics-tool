CFLAGS = -O3 -Wall -lm -I../../../../../../lib/c

metric-provider-binary: source.c
	gcc ../../../../../../lib/c/parse_int.o $< $(CFLAGS) -o $@
	sudo chown root $@
	sudo chmod u+s $@
