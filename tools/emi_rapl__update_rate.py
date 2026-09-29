"""
Misst wie oft das RAPL-Register sich tatsächlich aktualisiert.
Ruft die EMI-Binary mit 1ms Interval auf und misst die Zeit zwischen
aufeinanderfolgenden *verschiedenen* Werten.
"""
import csv
import subprocess
import statistics
from pathlib import Path

GMT_ROOT = Path(__file__).resolve().parent.parent
BINARY   = GMT_ROOT / "metric_providers/cpu/energy/rapl/emi/component/metric-provider-binary.exe"

INTERVAL_MS  = 1      # so schnell wie möglich samplen
DURATION_S   = 10     # 10 Sekunden

import subprocess
import statistics
import time
from pathlib import Path

GMT_ROOT = Path(__file__).resolve().parent.parent
BINARY   = GMT_ROOT / "metric_providers/cpu/energy/rapl/emi/component/metric-provider-binary.exe"

INTERVAL_MS = 5
DURATION_S  = 10

def main():
    print(f"Running EMI binary at {INTERVAL_MS}ms for ~{DURATION_S}s ...")

    proc = subprocess.Popen(
        [str(BINARY), "-i", str(INTERVAL_MS)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    lines = []
    deadline = time.time() + DURATION_S
    while time.time() < deadline:
        line = proc.stdout.readline()
        if line:
            lines.append(line.strip())

    proc.kill()
    proc.wait()

    parsed = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 2:
            try:
                parsed.append((int(parts[0]), int(parts[1])))
            except ValueError:
                pass

    print(f"  Parsed {len(parsed)} samples")

    update_deltas_us = []
    for i in range(1, len(parsed)):
        if parsed[i][1] != parsed[i-1][1]:
            delta = parsed[i][0] - parsed[i-1][0]
            update_deltas_us.append(delta)

    if not update_deltas_us:
        print("  No value changes detected!")
        return

    print(f"\n=== RAPL Register Update Rate ===")
    print(f"  Value changes : {len(update_deltas_us)}")
    print(f"  Min  delta    : {min(update_deltas_us)/1000:.2f} ms")
    print(f"  Max  delta    : {max(update_deltas_us)/1000:.2f} ms")
    print(f"  Mean delta    : {statistics.mean(update_deltas_us)/1000:.2f} ms")
    print(f"  Median delta  : {statistics.median(update_deltas_us)/1000:.2f} ms")
    print(f"  Stdev         : {statistics.stdev(update_deltas_us)/1000:.2f} ms")
    csv_path = GMT_ROOT / "tools" / "emi_rapl_update_rate.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["delta_us", "delta_ms"])
        for d in update_deltas_us:
            writer.writerow([d, round(d / 1000, 3)])
    print(f"\n  Saved {len(update_deltas_us)} deltas → {csv_path}")
if __name__ == "__main__":
    main()