## Intro

This metric provider uses the lm-sensors package to expose multiple values to the green metric tool.

If you call the program without a parameter it will output all the sensors/ values that it can expose.
This is only for debugging! The proper way to call the code is by specifying a label.

```
./metric-provider-binary CPU -i 100
```

Please note that the values might seam a little high. This is because we all values as integers and not floats. So
a reading of 60.25 degrees will become 6025.

A lot of the code is copied from https://github.com/lm-sensors/lm-sensors/tree/master/prog/sensors



## Install

You will need  `sudo apt install libsensors-dev` installed on a Debian based distro.