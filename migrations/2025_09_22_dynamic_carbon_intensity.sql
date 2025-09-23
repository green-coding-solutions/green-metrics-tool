-- Migration: Add dynamic carbon intensity capabilities and separate metric names
-- Date: 2025-09-22
-- Description: Adds measurement.use_dynamic_grid_carbon_intensity and measurement.grid_carbon_intensity_location
--              to user updateable_settings and separates static/dynamic carbon intensity metrics

-- Add new settings to updateable_settings for all users (excluding system user 0)
UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{user,updateable_settings}',
    (
        COALESCE(capabilities->'user'->'updateable_settings', '[]'::jsonb) ||
        '["measurement.use_dynamic_grid_carbon_intensity", "measurement.grid_carbon_intensity_location"]'::jsonb
    ),
    true
) WHERE id != 0;

-- Set default value for use_dynamic_grid_carbon_intensity (disabled by default)
UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{measurement,use_dynamic_grid_carbon_intensity}',
    'false',
    true
) WHERE id != 0;

-- Set default value for grid_carbon_intensity_location (default to DE)
UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{measurement,grid_carbon_intensity_location}',
    '"DE"',
    true
) WHERE id != 0;
