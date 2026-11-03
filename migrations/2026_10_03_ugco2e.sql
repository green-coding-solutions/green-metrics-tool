UPDATE phase_stats
SET unit = 'ugCO2e'
WHERE unit = 'ug' AND metric NOT LIKE 'custom_%';
