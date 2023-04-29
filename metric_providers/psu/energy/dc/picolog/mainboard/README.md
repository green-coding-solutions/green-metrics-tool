# Building

Just run `make`.

It will require `sudo` rights as it will set the UID bit.

# Running

Just run: 
```bash
./metric-provider-binary -i 61`.
```

Please use always the resolution of *61 ms* as the provider is configured
to set up the streaming channel for this resolution.


## Overhead warning

This metric provider has high overhead when used as it draws significant energy
through the USB port.

Please check [the documentation](https://docs.green-coding.org/docs/measuring/metric-providers/psu-energy-dc-machine/) for details.