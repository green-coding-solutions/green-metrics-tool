# Information

See https://docs.green-coding.io/docs/measuring/metric-providers/psu-energy-ac-ipmi-machine/ for details.

This provider uses [IPMI](https://www.intel.com/content/www/us/en/products/docs/servers/ipmi/ipmi-home.html) to get  
the current machine power statistics.

The provider is only a fronted to the underlying interface and although you can put in higher sampling resolutions (< 1 s) the data might not change bc the underlying implementation only supplies aggregated data over longer sample periods.

Please check with your underlying hardware specifications what the minimal sampling is you can retrieve.
