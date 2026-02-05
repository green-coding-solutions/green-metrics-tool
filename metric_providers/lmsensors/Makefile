GMT_LIB_DIR = ../../lib/c
PROGRAM = metric-provider-binary
SOURCES = source.c chips.c
GLIBLIB = $(shell pkg-config --libs glib-2.0)
GLIBGLAGS = $(shell pkg-config --cflags glib-2.0)
CFLAGS = -O3 -Wall -Werror -Llib -lsensors $(GLIBLIB) $(GLIBGLAGS) -I$(GMT_LIB_DIR)

$(PROGRAM): $(SOURCES) $(GMT_LIB_DIR)/gmt-lib.o $(GMT_LIB_DIR)/gmt-lib.h
	gcc $(GMT_LIB_DIR)/gmt-lib.o $(SOURCES) $(CFLAGS) -o $(PROGRAM)

binary: $(PROGRAM)

lint:
	cpplint *.c *.h

debug: $(SOURCES) $(GMT_LIB_DIR)/gmt-lib.o $(GMT_LIB_DIR)/gmt-lib.h
	gcc $(GMT_LIB_DIR)/gmt-lib.o $(SOURCES) $(CFLAGS) -g -o $(PROGRAM)
