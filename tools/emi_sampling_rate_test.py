"""
EMI Sampling Rate Test Runner
Runs the same GMT scenario at different sampling_rate values for cpu_energy_rapl_emi_component,
stores run_ids + metadata in SQLite, exports phase_stats to CSV.

Usage:
    python tools/emi_sampling_rate_test.py

Results:
    tools/emi_sampling_rate_results.db   (SQLite with run metadata)
    tools/emi_sampling_rate_results.csv  (phase_stats per run)
"""

import subprocess
import sqlite3
import re
import sys
import time
from pathlib import Path
from datetime import datetime

import psycopg2
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
GMT_ROOT       = Path(__file__).resolve().parent.parent          # gmt-windows-2.1
RUNNER         = GMT_ROOT / "runner.py"
CONFIG_YML     = GMT_ROOT / "config.yml"
RESULTS_DB     = GMT_ROOT / "tools" / "emi_sampling_rate_results.db"
RESULTS_CSV    = GMT_ROOT / "tools" / "emi_sampling_rate_results.csv"

# Scenario to run (adjust path as needed)
SCENARIO_URI      = str(Path(r"C:\Users\jahns\Documents\CASO\compression-benchmarks"))
SCENARIO_FILENAME = "extended_scenarios/usage_scenario-brotli-compress_10mb.yml"

SAMPLING_RATES = [99, 50, 20, 10, 7, 5]   # ms — 5ms known to fail (driver ~6.5ms floor)
ITERATIONS     = 3                          # GMT runs per sampling_rate

# PostgreSQL
PG_DSN = "host=localhost port=9573 dbname=green-coding user=postgres password=test1234"
# ──────────────────────────────────────────────────────────────────────────────


def get_latest_run_ids(pg_conn, n: int) -> list[str]:
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id FROM runs ORDER BY created_at DESC LIMIT %s", (n,))
        return [str(row[0]) for row in cur.fetchall()]


def set_emi_sampling_rate(rate: int) -> bool:
    text = CONFIG_YML.read_text(encoding="utf-8")
    pattern = r"(cpu_energy_rapl_emi_component:\s*\n\s*sampling_rate:\s*)\d+"
    new_text, count = re.subn(pattern, rf"\g<1>{rate}", text)
    if count == 0:
        print("  WARNING: cpu_energy_rapl_emi_component sampling_rate not found in config.yml")
        return False
    CONFIG_YML.write_text(new_text, encoding="utf-8")
    print(f"  config.yml → sampling_rate: {rate}")
    return True


def init_db(db_path: Path):
    con = sqlite3.connect(db_path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS emi_runs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            sampling_rate INTEGER NOT NULL,
            run_id        TEXT    NOT NULL,
            scenario      TEXT,
            iterations    INTEGER,
            ts            TEXT,
            status        TEXT
        )
    """)
    con.commit()
    return con


def run_scenario(sampling_rate: int, pg_conn, sqlite_con):
    print(f"\n{'='*60}")
    print(f"Sampling rate: {sampling_rate} ms  ({ITERATIONS} iterations)")
    print(f"{'='*60}")

    if not set_emi_sampling_rate(sampling_rate):
        return

    before_ids = set(get_latest_run_ids(pg_conn, 20))

    cmd = [
        sys.executable, str(RUNNER),
        "--uri",        SCENARIO_URI,
        "--filename",   SCENARIO_FILENAME,
        "--iterations", str(ITERATIONS),
    ]
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False, text=True, cwd=str(GMT_ROOT))

    run_status = "OK" if result.returncode == 0 else "RUNNER_ERROR"
    if result.returncode != 0:
        print(f"  WARNING: runner exited with code {result.returncode} (data may still be in DB)")

    time.sleep(2)  # give PostgreSQL time to commit

    after_ids = set(get_latest_run_ids(pg_conn, 20))
    new_ids   = list(after_ids - before_ids)

    if not new_ids:
        print("  WARNING: no new run_ids found in PostgreSQL")
        return

    print(f"  New run_ids: {new_ids}")
    ts = datetime.now().isoformat(timespec="seconds")
    for run_id in new_ids:
        sqlite_con.execute(
            "INSERT INTO emi_runs (sampling_rate, run_id, scenario, iterations, ts, status) VALUES (?,?,?,?,?,?)",
            (sampling_rate, run_id, SCENARIO_FILENAME, ITERATIONS, ts, run_status)
        )
    sqlite_con.commit()
    print(f"  Saved {len(new_ids)} run_id(s) → {RESULTS_DB.name}")


def export_to_csv(sqlite_path: Path, csv_path: Path):
    """Query phase_stats for all recorded run_ids and export to CSV."""
    print(f"\nExporting results to CSV...")

    con = sqlite3.connect(sqlite_path)
    runs_df = pd.read_sql("SELECT * FROM emi_runs", con)
    con.close()

    if runs_df.empty:
        print("  No runs recorded — nothing to export.")
        return

    ids = tuple(runs_df['run_id'].tolist())
    pg  = psycopg2.connect(PG_DSN)
    with pg.cursor() as cur:
        cur.execute("""
            SELECT run_id::text, phase, metric, detail_name,
                   value, unit, sampling_rate_95p
            FROM phase_stats
                WHERE run_id = ANY(%s::uuid[])
              AND metric = 'cpu_energy_rapl_emi_component'
        """, (list(ids),))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    pg.close()
    phase_df = pd.DataFrame(rows, columns=cols)

    if phase_df.empty:
        print("  WARNING: no phase_stats found for recorded run_ids (runs may have failed before commit).")
        runs_df.to_csv(csv_path, index=False)
        print(f"  Saved run metadata only → {csv_path}")
        return

    merged = phase_df.merge(
        runs_df[['run_id', 'sampling_rate', 'status', 'ts']],
        on='run_id', how='left'
    )
    merged.to_csv(csv_path, index=False)
    print(f"  Saved {len(merged)} rows → {csv_path}")


def main():
    print("EMI Sampling Rate Test")
    print(f"Scenario : {SCENARIO_FILENAME}")
    print(f"Rates    : {SAMPLING_RATES} ms")
    print(f"Results  : {RESULTS_DB}")

    original_text = CONFIG_YML.read_text(encoding="utf-8")
    pg_conn       = psycopg2.connect(PG_DSN)
    sqlite_con    = init_db(RESULTS_DB)

    try:
        for rate in SAMPLING_RATES:
            run_scenario(rate, pg_conn, sqlite_con)
    finally:
        CONFIG_YML.write_text(original_text, encoding="utf-8")
        print("\nconfig.yml restored.")
        pg_conn.close()
        sqlite_con.close()

    export_to_csv(RESULTS_DB, RESULTS_CSV)
    print(f"\nDone.")
    print(f"  DB  → {RESULTS_DB}")
    print(f"  CSV → {RESULTS_CSV}")


if __name__ == "__main__":
    main()
