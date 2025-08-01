CFLAGS = -O3 -Wall -Werror -lm -I../../../../../lib/c

metric-provider-binary: source.c
	gcc ../../../../../lib/c/gmt-lib.o $< $(CFLAGS) -o $@
	sudo chown root $@
	sudo chmod u+s $@
