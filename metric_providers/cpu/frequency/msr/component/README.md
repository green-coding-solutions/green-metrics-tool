# cpu_frequency_msr_component

Reports CPU frequencies in Hz read directly from MSRs (`/dev/cpu/*/msr`).

| detail_name | Source | Semantics | Enabled |
|---|---|---|---|
| `Core_<cpu_id>` | `APERF` / `MPERF` × `base_ghz` | Average over the sampling interval (busy time only) | Always |
| `Uncore_Package_<id>` | `MSR_UNCORE_PERF_STATUS` (0x621), ratio × 100 MHz | Instantaneous snapshot at read time | `uncore: true` (binary switch `-u`) |

- Set `base_ghz` to the nominal (non-turbo) base clock of your CPU.
- Core frequency works on Intel and AMD. Uncore frequency is Intel only (Haswell and newer); the
  provider check fails if `uncore: true` is set on an unsupported CPU.
- Requires the `msr` kernel module (`sudo modprobe msr`) and bare metal.

For the same metrics via the perf subsystem see `cpu_frequency_perf_component`.
