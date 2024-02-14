# Information

See https://docs.green-coding.io/docs/measuring/metric-providers/psu-energy-ac-ipmi-machine/ for details.

This provider uses [IPMI](https://www.intel.com/content/www/us/en/products/docs/servers/ipmi/ipmi-home.html) to get  
the current machine power statistics.

It requires specific hardware to run and we have also identified a delay in the readings, close to one second.  
This provider is currently a proof of concept, and is uncertain if it will be developed further.
