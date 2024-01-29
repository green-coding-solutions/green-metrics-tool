# Into

A metric provider for the powerspy2 energy meter. The majority of the work is based on Volkers work that can be found
under https://invent.kde.org/vkrause/powerspy2-tools. Some influence from https://github.com/patrickmarlier/powerspy.py

The protocol documentation can be found under:
https://www.alciom.com/wp-content/uploads/2018/04/LG0838-003-powerspy-protocol-specification-1G.pdf

Full documentation of this provider can be found on our main docs page:
https://docs.green-coding.io/docs/measuring/metric-providers/psu-energy-ac-powerspy2/

## Setup

A detailed description can be found under https://invent.kde.org/vkrause/powerspy2-tools

1) You will need to install `pip install pyserial==3.5` into your environment.

2) You need to connect the powerspy through your operating systems bluetooth framework. For Ubuntu you can either do
this through `$ blueman-manager` or `bluetoothctl`. See https://simpleit.rocks/linux/shell/connect-to-bluetooth-from-cli/
for more details.

3) Once you are connected you should be able to connect to the serial console by running
`# rfcomm connect /dev/rfcomm0 <addr> 1`
where addr is the mac address of your powerspy2 device. You can query this through `bluetoothctl devices`.
Please note that you will have to do this as root!

A one-liner, if your PowerSpy2 is already paired with the OS is:
`bluetoothctl devices | awk '$0 ~ /PowerSpy/ {print $2}' | xargs -I % sudo rfcomm connect /dev/rfcomm0 % 1`

However, if you want to start the bluetooth connection via SSH we recommend you start it in the background and disown it:

`sudo rfcomm connect /dev/rfcomm0 DEVICE_MAC 1 &`

then do: `disown -h`

4) Make the rfcomm device read and writeable by all as root. `sudo chmod 777 /dev/rfcomm0`
This is potentially a security problem if you are on a shared machine!

5) Please try running the metrics provider first to see if everything works.

## Notes

Please note, that this is all very experimental and the connections are not very stable and crashes are quite common.
Normally it is enough to restart the bluetooth demon and rerun the rfcomm command. The powerspy also sometimes gets
into a non responsive state and needs rebooting.