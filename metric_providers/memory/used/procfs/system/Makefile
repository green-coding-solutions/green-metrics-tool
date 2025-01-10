CFLAGS = -O3 -Wall -Werror -I../../../../../lib/c

metric-provider-binary: source.c
	gcc ../../../../../lib/c/parse_int.o $< $(CFLAGS) -o $@
