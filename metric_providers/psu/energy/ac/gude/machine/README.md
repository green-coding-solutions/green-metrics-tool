Slimmed down version of check_gude.py from https://github.com/gudesystems/check_gude.py
for the Blauer Engel für Software Measurements
===============

This script expects the GUDE Powermeter to be fixed on the IP 192.168.178.32

- Create **venv**: `python3 -m venv venv`
- Activate: `source venv/bin/activate`
- Install requests: `pip3 install requests`
- Run: `python3 check_gude.py`


This metric providers is no longer officially mainted by us anymore, but remains here for backwards compatability.

This provider was initially meant to be used with the same power meter the [Blauer Engel](https://eco.kde.org/blog/2022-05-30-sprint-lab-setup/) team used, the [Gude Expert Power Control 1202](https://gude-systems.com/en/products/expert-power-control-1202/). Please find technical specifications on the manufactor's website.