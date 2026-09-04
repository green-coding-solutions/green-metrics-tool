# Information

This provider is a variant of `network_connections_tcpdump_system` that captures traffic only
on the host-side veth interfaces of the containers belonging to the current run, instead of
system-wide traffic on the host's default interface, and attributes every captured packet back
to the container it belongs to.

For each running container it resolves the host-side veth interface(s) backing its network
interface(s) (a container attached to more than one docker network contributes more than one
veth) by:

1. Listing its network interfaces and reading each one's `iflink` (peer ifindex) via
   `docker exec <container_id> ls /sys/class/net` / `cat /sys/class/net/<iface>/iflink`
2. Matching that peer ifindex against the host's `/sys/class/net/veth*/ifindex` entries

Docker does not expose this host-veth <-> container-interface mapping anywhere in its API or
`inspect` output (it's a kernel-level detail), so it has to be derived this way. `docker exec`
is used rather than entering the container's network namespace directly from the host (e.g. via
`nsenter`) so that the already-privileged docker daemon performs the namespace entry on our
behalf - this only needs docker socket access, the same privilege level GMT already requires
for everything else, rather than `CAP_SYS_ADMIN`/root on the host. One consequence: the
container image needs `ls` and `cat` available for this to work - a fully scratch/distroless
image with no coreutils cannot be resolved this way.

It then runs a single `tcpdump -i any` process filtered down to just those veths via a BPF
`ifname` filter (`ifname vethAAA or ifname vethBBB or ...`), and uses tcpdump's per-line
interface tagging (available with the `LINUX_SLL2` capture format used for `-i any` captures)
to group parsed packets by the container that generated them.

This provider is Linux-only and requires `tcpdump` >= 4.99 (for `ifname` BPF filter support and
`LINUX_SLL2` per-line interface tagging).

See also `metric_providers/network/connections/tcpdump/system/README.md` for the shared
packet-parsing format documentation (`parse_tcpdump`/`generate_stats_string`), which this
provider reuses unchanged.

See https://docs.green-coding.io/docs/measuring/metric-providers/network-connections-tcpdump-container/ for further details.
