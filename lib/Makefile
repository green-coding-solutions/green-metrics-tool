# This is copied from https://raw.githubusercontent.com/intel/sgx-software-enable/master/Makefile
# and then modified a little to fit our needs

CC=gcc

all: sgx_enable

%.o: %.c
	$(CC) -c $<

sgx_enable: sgx_enable.o
	$(CC) -o $@ $?

clean:
	rm -f *.o sgx_enable
