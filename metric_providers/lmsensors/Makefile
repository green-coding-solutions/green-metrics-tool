LIB_C = ../../lib/c
PROGRAM = metric-provider-binary
SOURCES = source.c chips.c
GLIBLIB = $(shell pkg-config --libs glib-2.0)
GLIBGLAGS = $(shell pkg-config --cflags glib-2.0)
CFLAGS = -O3 -Wall -Werror -Llib -lsensors $(GLIBLIB) $(GLIBGLAGS) -I$(LIB_C)

$(PROGRAM): $(SOURCES) $(LIB_C)/gmt-lib.o $(LIB_C)/gmt-lib.h
	gcc $(LIB_C)/gmt-lib.o $(SOURCES) $(CFLAGS) -o $(PROGRAM)

binary: $(PROGRAM)

lint:
	cpplint *.c *.h

debug: $(SOURCES) $(LIB_C)/gmt-lib.o $(LIB_C)/gmt-lib.h
	gcc $(LIB_C)/gmt-lib.o $(SOURCES) $(CFLAGS) -g -o $(PROGRAM)
