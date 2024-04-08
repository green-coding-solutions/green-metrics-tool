# Building

Just run `make`.

It will require `sudo` rights as it will set the UID bit.

# Running

Just run `./metric-provider-binary -d`.

You can specify a resoltion for the output frequency in *ms* through the `-i` flag.

Example:

```bash
./metric-provider-binary -p -i 100
```

# Documentation

For details and output format please look at https://docs.green-coding.io/docs/measuring/metric-providers/psu-energy-dc-rapl-msr-machine/
