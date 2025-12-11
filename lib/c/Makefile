CFLAGS = -O3 -Wall

all: gmt-lib.o gmt-container-lib.o

gmt-lib.o: gmt-lib.c gmt-lib.h
	gcc -c $< $(CFLAGS) -o $@

gmt-container-lib.o: gmt-container-lib.c gmt-container-lib.h
	gcc -c $< $(CFLAGS) -o $@