LIB_C = ../../../../../../lib/c
CFLAGS = -O3 -Wall -Werror -lm -I$(LIB_C)

metric-provider-binary: source.c $(LIB_C)/gmt-lib.o $(LIB_C)/gmt-lib.h
	gcc $(LIB_C)/gmt-lib.o $< $(CFLAGS) -o $@
	sudo chown root $@
	sudo chmod u+s $@
