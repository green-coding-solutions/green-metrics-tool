WITH times as (
    SELECT id, value, time, (time - LAG(time) OVER (ORDER BY project_id ASC, metric ASC, detail_name ASC, time ASC)) AS diff, unit
    FROM stats
    WHERE unit = 'mW'
    ORDER BY project_id ASC, metric ASC, detail_name ASC, time ASC
    LIMIT 10000

) UPDATE stats SET value = (value * (SELECT diff FROM times where id = stats.id) / (1000000)), unit = 'mJ'
WHERE EXISTS (SELECT id FROM times WHERE times.id = stats.id);

-- this code assumes that all times are in us as is default for the GMT