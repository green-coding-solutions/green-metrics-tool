# Information

This provider is a variant of `network_connections_tcpdump_system` that captures traffic only
on the host-side veth interfaces of the containers belonging to the current run, instead of
system-wide traffic on the host's default interface, and attributes every captured packet back
to the container it belongs to.

For each running container it resolves the host-side veth interface(s) backing its network
interface(s) (a container attached to more than one docker network contributes more than one
veth) by:

1. Reading the container's PID via `docker inspect -f '{{.State.Pid}}' <container_id>`
2. Listing its network interfaces and reading each one's `iflink` (peer ifindex) via
   `nsenter -t <pid> -n -- ...`
3. Matching that peer ifindex against the host's `/sys/class/net/veth*/ifindex` entries

It then runs a single `tcpdump -i any` process filtered down to just those veths via a BPF
`ifname` filter (`ifname vethAAA or ifname vethBBB or ...`), and uses tcpdump's per-line
interface tagging (available with the `LINUX_SLL2` capture format used for `-i any` captures)
to group parsed packets by the container that generated them.

This provider is Linux-only and requires:
- `tcpdump` >= 4.99 (for `ifname` BPF filter support and `LINUX_SLL2` per-line interface tagging)
- `nsenter` (part of `util-linux`)

See also `metric_providers/network/connections/tcpdump/system/README.md` for the shared
packet-parsing format documentation (`parse_tcpdump`/`generate_stats_string`), which this
provider reuses unchanged.

See https://docs.green-coding.io/docs/measuring/metric-providers/network-connections-tcpdump-container/ for further details.
