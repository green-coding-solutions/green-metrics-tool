CFLAGS = -o3 -Wall -lm  -L./ -lpicohrdl -lc

metric-provider-binary: source.c
	gcc $< $(CFLAGS) -o $@
	sudo rm -f /usr/lib/libpicohrdl.so.2
	sudo ln -s $(PWD)/tools/metric_providers/psu/energy/dc/system/libpicohrdl.so.2 /usr/lib/
