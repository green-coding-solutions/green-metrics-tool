PROGRAM = metric-provider-binary
SOURCES = source.c chips.c
GLIBLIB = $(shell pkg-config --libs glib-2.0)
GLIBGLAGS = $(shell pkg-config --cflags glib-2.0)
CFLAGS = -O3 -Wall -Llib -lsensors $(GLIBLIB) $(GLIBGLAGS) -I../../lib/c

binary:
	gcc ../../lib/c/parse_int.o $(SOURCES) $(CFLAGS) -o $(PROGRAM)

lint:
	cpplint *.c *.h

debug:
	gcc ../../lib/c/parse_int.o $(SOURCES) $(CFLAGS) -g -o $(PROGRAM)
