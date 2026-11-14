-- Run listings (api/scenario_runner.py, api/software.py) do ORDER BY r.created_at DESC, which previously sorted the whole runs table
CREATE INDEX IF NOT EXISTS runs_created_at_idx ON runs(created_at);
