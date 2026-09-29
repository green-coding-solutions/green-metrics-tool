# EMI Driver Sampling Rate — Test Report

**Date:** 2026-09-25  
**Tester:** Max Jahns  
**GMT Version:** gmt-windows-2.1  
**PR:** #1801

---

## Summary

The Windows Energy Meter Interface (EMI) driver can reliably sample RAPL energy data down to **~2 ms** at the hardware level. The practical minimum for the GMT runner is **10 ms**, limited by Python subprocess orchestration overhead — not the driver itself.

---

## Test Setup

- **Hardware:** Windows 11, Intel/AMD CPU with RAPL support
- **Scenario:** brotli 10 MB compression (`usage_scenario-brotli-compress_10mb.yml`)
- **Binary:** `metric_providers/cpu/energy/rapl/emi/component/metric-provider-binary.exe`
- **GMT check:** `base.py` raises `RuntimeError` if `sampling_rate_95p >= configured_rate × 1.2` (20% tolerance)

---

## Note: Corrected Repeat-Ratio Metric

The initial version of `tools/emi_interval_test.ps1` calculated repeat-ratio incorrectly:

```powershell
# WRONG — counts non-consecutive value coincidences across the whole window
$uniqueCount = ($values | Sort-Object -Unique).Count
$repeatRatio = 1 - ($uniqueCount / $sampleCount)
```

This inflated the repeat-ratio significantly (e.g. 85.8% at 1 ms, 33.7% at 5 ms) because energy values that happened to be numerically equal at different points in time were counted as duplicates, even if they were not consecutive.

The correct metric counts only **consecutive** duplicate values — i.e. how often the next sample is identical to the previous one, which is the actual indicator of the RAPL register not having updated between two samples:

```powershell
# CORRECT — consecutive duplicates only
$consecutiveRepeats = 0
for ($i = 1; $i -lt $values.Count; $i++) {
    if ($values[$i] -eq $values[$i - 1]) { $consecutiveRepeats++ }
}
$repeatRatio = if ($sampleCount -gt 1) { [math]::Round($consecutiveRepeats / ($sampleCount - 1), 3) } else { 0.0 }
```

With the corrected metric, consecutive duplicate rates are below 0.5% at all tested intervals, confirming that the EMI driver delivers new values on virtually every sample.

---

## Test 1 — Binary Direct Test (no GMT overhead)

The EMI binary was called directly at intervals from 1–99 ms, 10 runs × 5 seconds each.  
Repeat-ratio measures **consecutive** duplicate values (corrected metric per code review).

| Rate (ms) | OK Runs | Consec. Repeat-Ratio | Status |
|-----------|---------|----------------------|--------|
| 1 | 10/10 | 0.4 % | OK |
| 5 | 10/10 | 0.2 % | OK |
| 10 | 10/10 | 0.2 % | OK |
| 20 | 10/10 | 0.2 % | OK |
| 50 | 10/10 | 0.1 % | OK |
| 65 | 10/10 | 0.1 % | OK |
| 80 | 10/10 | 0.1 % | OK |
| 99 | 10/10 | 0.0 % | OK |

**Finding:** The EMI driver itself is stable at all tested rates down to 1 ms. Consecutive duplicate values are negligible at all rates.

---

## Test 2 — RAPL Register Update Rate

The EMI binary was run at 1 ms to measure how often the underlying RAPL hardware register actually updates.

| Metric | Value |
|--------|-------|
| Value changes | 5031 / 5082 samples (99.0 %) |
| Min delta | 1.06 ms |
| Max delta | 3.56 ms |
| Mean delta | 1.97 ms |
| **Median delta** | **2.00 ms** |
| Stdev | 0.18 ms |

**Finding:** The RAPL hardware register updates approximately every **2 ms**. This is the true hardware floor — not 8–9 ms as previously assumed.

---

## Test 3 — GMT Runner Test

The full GMT runner was executed at sampling rates from 5–99 ms (3 iterations each, brotli 10 MB).  
`sampling_rate_95p` is the metric GMT uses to validate the provider.

| Rate (ms) | Actual 95p (ms) | Overhead | Energy RUNTIME | GMT Status |
|-----------|----------------|----------|----------------|------------|
| 5 | 6.5 | +30 % | — | **RUNNER_ERROR** |
| 7 | 8.5 | +21 % | — | **RUNNER_ERROR** |
| **10** | **11.66** | **+16.6 %** | **309 ± 24 mJ** | **PASS** |
| 20 | 21.3 | +6.5 % | 299 ± 15 mJ | PASS |
| 50 | 51.4 | +2.8 % | 308 ± 10 mJ | PASS |
| 99 | 100.73 | +0.7 % | 317 ± 21 mJ | PASS |

**Finding:** GMT fails below ~10 ms because Python subprocess orchestration adds ~1–2 ms overhead on top of the binary's timing. At 7 ms configured, the actual 95p is 8.5 ms (+21%), exceeding the 20% tolerance. Energy values are consistent across all passing rates — sampling rate does not affect measurement accuracy.

---

## Test 4 — GMT Internal Timestamp Analysis

`base.py` was temporarily instrumented to export raw per-sample timestamp deltas before cleanup.  
This confirms the distribution of actual intervals as seen by the GMT runner.

| Provider | Config | Median | P95 | Stdev | P95 Overhead | GMT check |
|----------|--------|--------|-----|-------|--------------|-----------|
| EMI | 99 ms | 99.91 ms | 100.73 ms | 1.40 ms | +0.7 % | PASS |
| EMI | 10 ms | 10.81 ms | 11.66 ms | 1.16 ms | +16.6 % | PASS |
| cpu_utilization_win32 | 99 ms | 99.88 ms | 100.79 ms | 2.52 ms | +0.8 % | PASS |
| cpu_utilization_ntapi | 99 ms | 102.99 ms | 106.19 ms | 2.71 ms | +6.2 % | PASS |

At 10 ms, 97.8 % of samples arrive within 12 ms (within 20% tolerance). Outliers above 15 ms account for only 0.7 % of samples and are caused by Windows scheduler jitter.

---

## Appendix: Temporary base.py Instrumentation

To capture raw per-sample timestamp deltas from inside the GMT runner, two lines were temporarily added to `metric_providers/base.py` in `_add_and_validate_sampling_rate_and_jitter()` and then removed after the test runs.

**Location:** after line 141 (after `sampling_rate_95p` is calculated, before `sampling_rate` is dropped)

```python
# ADDED temporarily for debug — removed after testing
import pathlib; _dbg = pathlib.Path(__file__).parent.parent / 'tools' / f'debug_sampling_{self._metric_name}.csv'
df[['time', 'sampling_rate_95p']].assign(sampling_rate_raw=df.groupby(grouping_columms)['time'].diff()).to_csv(_dbg, index=False)
```

This wrote a CSV file to `tools/debug_sampling_<metric_name>.csv` after each run containing:
- `time` — absolute timestamp (µs) of each sample
- `sampling_rate_95p` — the 95th percentile value GMT uses for validation
- `sampling_rate_raw` — the raw per-sample interval (diff of consecutive timestamps in µs)

The files were created for all active metric providers during a run:
- `debug_sampling_cpu_energy_rapl_emi_component.csv`
- `debug_sampling_cpu_utilization_win32_system.csv`
- `debug_sampling_cpu_utilization_ntapi_core.csv`

**The change was reverted after testing.** `base.py` is back to its original state.

---

## Conclusions

| Layer | Minimum |
|-------|---------|
| RAPL Hardware register | ~2 ms |
| EMI driver (binary direct) | ~2 ms |
| GMT runner (Python overhead) | **10 ms** |

The bottleneck is the GMT Python layer, not the EMI driver. The recommended minimum `sampling_rate` for `cpu_energy_rapl_emi_component` is **10 ms**. Configuring values below 10 ms will cause `base.py` to raise a `RuntimeError` due to the 20% tolerance check on `sampling_rate_95p`.
