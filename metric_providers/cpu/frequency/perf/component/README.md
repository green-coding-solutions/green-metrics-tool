# cpu_frequency_perf_component

Reports CPU frequencies in Hz via the `perf_event_open()` interface. Same metrics as
`cpu_frequency_msr_component`, but read through the kernel's perf subsystem instead of `/dev/cpu/*/msr`.

| detail_name | Source | Semantics | Enabled |
|---|---|---|---|
| `Core_<cpu_id>` | perf `msr` PMU: `aperf` / `mperf` × `base_ghz` | Average over the sampling interval (busy time only) | Always |
| `Uncore_Package_<id>[_Die_<id>]` | uncore PMU clockticks / `time_running` | Average over the sampling interval | `uncore: true` (binary switch `-u`) |

- Set `base_ghz` to the nominal (non-turbo) base clock of your CPU.
- The `msr` PMU counters are free running: they work on Intel and AMD and do not occupy
  general purpose PMU counters. No `msr` kernel module needed.
- Uncore is Intel only. AMD has no public uncore clock counter.
- Because `time_running` comes from the kernel, uncore counter multiplexing is handled automatically.
  If an uncore counter did not run at all in an interval, no value is emitted for that interval.

## Uncore PMU auto-detection

The uncore PMU that exposes clockticks differs between Intel generations. These are tried in order:

| PMU | Event | Typical CPUs |
|---|---|---|
| `uncore_clock` | `clockticks` alias | Client, Ice Lake and newer |
| `uncore_cbox_0` | `clockticks` alias | Client, Sandy Bridge – Comet Lake |
| `uncore_ubox` | `event=0xff` (fixed UCLK counter) | Server, Haswell-EP and newer |
| `uncore_cha_0` | `clockticks` alias | Server, if the kernel exposes the alias |

If detection picks the wrong PMU or none, set it manually in `config.yml`:

```yaml
cpu_frequency_perf_component:
  sampling_rate: 99
  base_ghz: 2.4
  uncore: true
  uncore_pmu: uncore_cha_0   # name from /sys/bus/event_source/devices
  uncore_event: 'event=0x00' # optional, defaults to the PMU's clockticks alias
```

With `uncore: true` the `-c` check fails if the measured uncore value is outside 100 MHz – 10 GHz,
which usually means the event does not count uncore clocks.

## Requirements

- Bare metal. VMs usually expose neither the `msr` PMU nor uncore PMUs.
- The binary is installed setuid root. Otherwise it needs `CAP_PERFMON` or
  `/proc/sys/kernel/perf_event_paranoid <= 0`.
