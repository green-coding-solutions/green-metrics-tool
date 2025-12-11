GMT_LIB_DIR = ../../../../../lib/c
CFLAGS = -O3 -Wall -Werror -lc -lcurl -I$(GMT_LIB_DIR)

metric-provider-binary: source.c $(GMT_LIB_DIR)/gmt-lib.o $(GMT_LIB_DIR)/gmt-lib.h $(GMT_LIB_DIR)/gmt-container-lib.o $(GMT_LIB_DIR)/gmt-container-lib.h
	gcc $(GMT_LIB_DIR)/gmt-lib.o $(GMT_LIB_DIR)/gmt-container-lib.o $< $(CFLAGS) -o $@
	sudo chown root $@
	sudo chmod u+s $@