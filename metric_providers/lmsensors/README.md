## Intro

This metric provider uses the lm-sensors package to expose multiple values to the green metric tool.

If you call the program without a parameter it will output all the sensors/ values that it can expose.
This is only for debugging! The proper way to call the code is by specifying a label.

```
./metric-provider-binary -c coretemp-isa-0000 -f "Package id 0" -i 100
```

Please note that the values might seam a little high. This is because we all values as integers and not floats. So
a reading of 60.25 degrees will become 6025.

A lot of the code is copied from https://github.com/lm-sensors/lm-sensors/tree/master/prog/sensors


## Install

You will need  `sudo apt install -y lm-sensors libsensors-dev libglib2.0-0 libglib2.0-dev` installed on a Debian based distro. All the required packages should be installed during the `./install-linux.sh` run when installing Green Metrics Tool.

If you want the temperature metric provider to work you need to run the sensor detector

`sudo sensors-detect`

in order to detect all the sensors in your system. Once you have run this you should be able to run the `sensors` command and see your CPU temp. You can then use this output to look for the parameters you need to set in the config.yml. For example if sensors gives you:

```
coretemp-isa-0000
Adapter: ISA adapter
Package id 0:  +29.0°C  (high = +100.0°C, crit = +100.0°C)
Core 0:        +27.0°C  (high = +100.0°C, crit = +100.0°C)
Core 1:        +27.0°C  (high = +100.0°C, crit = +100.0°C)
Core 2:        +28.0°C  (high = +100.0°C, crit = +100.0°C)
Core 3:        +29.0°C  (high = +100.0°C, crit = +100.0°C)
```

Your config could be:

```
lmsensors.temperature.provider.LmSenorsTempProvider:
    resolution: 100
    chips: ['coretemp-isa-0000']
    features: ['Package id 0', 'Core 0', 'Core 1', 'Core 2', 'Core 3']
```

As the matching is open ended you could also only use 'Core' instead of naming each feature.

