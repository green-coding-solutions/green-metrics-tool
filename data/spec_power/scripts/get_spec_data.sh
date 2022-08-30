#!/bin/bash
spec_url="https://spec.org/power_ssj2008/results/power_ssj2008.html"
wget -S --header='Accept-Encoding:gzip' -nd -r -l 1 -A power_ssj*.html $spec_url

## remove files with no power data, and with shared hardware (done manually)