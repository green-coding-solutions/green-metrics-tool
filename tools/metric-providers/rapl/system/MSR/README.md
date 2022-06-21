## System configuration
In order for the `sudo` call to work an entry in the `/etc/sudoers` file is necessary.

```bash
sudo /usr/bin/stdbuf -oL PATH_TO_GREEN_METRICS_TOOL/tools/metric-providers/rapl/system/MSR/static-binary -i 100
```
