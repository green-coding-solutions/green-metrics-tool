PROGRAM = metric-provider-binary
SOURCES = source.c chips.c
GLIBLIB = $(shell pkg-config --libs glib-2.0)
GLIBGLAGS = $(shell pkg-config --cflags glib-2.0)
CFLAGS = -o3 -Wall -Llib -lsensors $(GLIBLIB) $(GLIBGLAGS)

binary:
	gcc $(SOURCES) $(CFLAGS) -o $(PROGRAM)

lint:
	cpplint *.c *.h

debug:
	gcc $(SOURCES) $(CFLAGS) -g -o $(PROGRAM)
