CFLAGS = -o3 -Wall -lm  -L./ -lpicohrdl -lc

metric-provider-binary: source.c
	sudo rm -f /usr/lib/libpicohrdl.so.2
	sudo ln -s $(PWD)/metric_providers/psu/energy/dc/picolog/system/libpicohrdl.so.2 /usr/lib/
	gcc $< $(CFLAGS) -o $@
	sudo chown root $@
	sudo chmod u+s $@