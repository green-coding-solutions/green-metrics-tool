#!/usr/bin/env python3
"""
gmt_export.py – Export GMT run data from PostgreSQL to CSV files.

Usage:
    # Export latest run:
    python3 gmt_export.py

    # Export specific run:
    python3 gmt_export.py --run-id 601dfac1-006c-46a9-b3d2-0152e1f39d66

    # Export last N runs:
    python3 gmt_export.py --last 5

    # Custom output directory:
    python3 gmt_export.py --out ~/exports/

Output files per run:
    {run_id}_phase_stats.csv   – aggregated metrics per phase (energy, power, CO2)
    {run_id}_measurements.csv  – raw time-series measurements
    {run_id}_meta.csv          – run metadata (name, date, duration)

Requirements:
    pip install psycopg2-binary pandas
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

try:
    import psycopg2
    import psycopg2.extras
    import pandas as pd
except ImportError:
    print("Missing dependencies. Run:")
    print("  pip install psycopg2-binary pandas")
    sys.exit(1)

DB_CONFIG = {
    'host':     'localhost',
    'port':     9573,
    'dbname':   'green-coding',
    'user':     'postgres',
    'password': 'test1234',  # set via env var PGPASSWORD or enter here
}

def connect():
    import os
    cfg = DB_CONFIG.copy()
    if pw := os.environ.get('PGPASSWORD'):
        cfg['password'] = pw
    return psycopg2.connect(**cfg)

def get_run_ids(conn, run_id=None, last=1):
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        if run_id:
            cur.execute("SELECT id FROM runs WHERE id = %s", (run_id,))
        else:
            cur.execute(
                "SELECT id FROM runs ORDER BY created_at DESC LIMIT %s",
                (last,)
            )
        rows = cur.fetchall()
    if not rows:
        print("No runs found.")
        sys.exit(1)
    return [str(r['id']) for r in rows]

def export_meta(conn, run_id, out_dir):
    query = """
        SELECT
            id,
            name,
            filename,
            created_at,
            start_measurement,
            end_measurement,
            (end_measurement - start_measurement) / 1e6 AS duration_seconds
        FROM runs
        WHERE id = %s
    """
    df = pd.read_sql(query, conn, params=(run_id,))
    path = out_dir / f"{run_id}_meta.csv"
    df.to_csv(path, index=False)
    print(f"  meta         → {path}")
    return df

def export_phase_stats(conn, run_id, out_dir):
    query = """
        SELECT
            phase,
            metric,
            detail_name,
            type,
            value,
            unit,
            max_value,
            min_value,
            sampling_rate_avg,
            sampling_rate_95p,
            sampling_rate_max
        FROM phase_stats
        WHERE run_id = %s
        ORDER BY phase, metric, detail_name
    """
    df = pd.read_sql(query, conn, params=(run_id,))

    # Convert units to human-readable
    df['value_human'] = df.apply(_convert_value, axis=1)
    df['unit_human']  = df.apply(_convert_unit, axis=1)

    path = out_dir / f"{run_id}_phase_stats.csv"
    df.to_csv(path, index=False)
    print(f"  phase_stats  → {path}")
    return df

def export_measurements(conn, run_id, out_dir):
    query = """
        SELECT
            mv.time,
            to_timestamp(mv.time / 1e6) AS timestamp,
            mv.value,
            mm.metric,
            mm.detail_name,
            mm.unit
        FROM measurement_values mv
        JOIN measurement_metrics mm ON mv.measurement_metric_id = mm.id
        WHERE mm.run_id = %s
        ORDER BY mv.time
    """
    try:
        df = pd.read_sql(query, conn, params=(run_id,))
        if df.empty:
            print(f"  measurements → skipped (no data)")
            return None
        path = out_dir / f"{run_id}_measurements.csv"
        df.to_csv(path, index=False)
        print(f"  measurements → {path} ({len(df)} rows)")
        return df
    except Exception as e:
        print(f"  measurements → skipped ({e})")
        return None

def export_notes(conn, run_id, out_dir):
    query = """
        SELECT note, time
        FROM notes
        WHERE run_id = %s
        AND (note LIKE 'Starting phase%%' OR note LIKE 'Ending phase%%')
        ORDER BY time
    """
    try:
        df = pd.read_sql(query, conn, params=(run_id,))
        if df.empty:
            print(f"  notes        → skipped (no data)")
            return None

        # event: 'start' oder 'end'
        df["event"] = df["note"].apply(
            lambda n: "start" if n.startswith("Starting") else "end"
        )

        # phase name bereinigen
        df["phase"] = df["note"].str.replace("Starting phase ", "", regex=False)
        df["phase"] = df["phase"].str.replace("Ending phase ", "", regex=False)
        df["phase"] = df["phase"].str.replace(r'\[UNPADDED\]', '', regex=True)
        df["phase"] = df["phase"].str.replace(r'\[PADDED\]', '', regex=True)
        df["phase"] = df["phase"].str.replace(r'[\[\]]', '', regex=True)
        df["phase"] = df["phase"].str.strip()

        # Dauer pro Phase berechnen
        starts = df[df["event"] == "start"].set_index("phase")["time"]
        ends   = df[df["event"] == "end"].set_index("phase")["time"]
        durations = ((ends - starts) / 1e6).rename("duration_seconds")
        df = df.join(durations, on="phase")

        path = out_dir / f"{run_id}_notes.csv"
        df.to_csv(path, index=False)
        print(f"  notes        → {path} ({len(df)} rows)")
        return df
    except Exception as e:
        print(f"  notes        → skipped ({e})")
        return None

def _convert_value(row):
    v = row['value']
    unit = row['unit']
    if unit == 'uJ':
        return round(v / 3_600_000_000, 6)  # uJ → Wh
    if unit == 'mW':
        return round(v / 1000, 3)            # mW → W
    if unit == 'ug':
        return round(v / 1_000_000, 6)       # ug → g
    return v

def _convert_unit(row):
    unit = row['unit']
    mapping = {'uJ': 'Wh', 'mW': 'W', 'ug': 'g'}
    return mapping.get(unit, unit)

def print_summary(df_phase, run_id):
    print(f"\n  Summary for run {run_id[:8]}...")
    rapl = df_phase[
        df_phase['metric'].str.contains('energy_rapl') &
        (df_phase['phase'] == df_phase[df_phase['metric'].str.contains('energy_rapl')]['phase'].iloc[-2]
         if len(df_phase[df_phase['metric'].str.contains('energy_rapl')]) > 0 else True)
    ]

    render = df_phase[
        df_phase['metric'].str.contains('energy_rapl') &
        ~df_phase['phase'].str.startswith('[')
    ]
    if not render.empty:
        print(f"\n  Render phase energy:")
        for _, row in render.iterrows():
            print(f"    {row['detail_name']:15} {row['value_human']:.4f} {row['unit_human']}")

def main():
    parser = argparse.ArgumentParser(description='Export GMT run data to CSV')
    parser.add_argument('--run-id', help='Specific run UUID')
    parser.add_argument('--last',   type=int, default=1, help='Export last N runs (default: 1)')
    parser.add_argument('--out',    default='.', help='Output directory (default: current dir)')
    parser.add_argument('--no-measurements', action='store_true', help='Skip raw measurements (faster)')
    args = parser.parse_args()

    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to PostgreSQL ({DB_CONFIG['host']}:{DB_CONFIG['port']})...")
    try:
        conn = connect()
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Tip: set PGPASSWORD environment variable")
        sys.exit(1)

    run_ids = get_run_ids(conn, args.run_id, args.last)
    print(f"Exporting {len(run_ids)} run(s) to {out_dir}/\n")

    for run_id in run_ids:
        print(f"Run: {run_id}")
        df_meta  = export_meta(conn, run_id, out_dir)
        df_phase = export_phase_stats(conn, run_id, out_dir)
        export_notes(conn, run_id, out_dir)
        if not args.no_measurements:
            export_measurements(conn, run_id, out_dir)
        print_summary(df_phase, run_id)
        print()

    conn.close()
    print("Done.")

if __name__ == '__main__':
    main()
