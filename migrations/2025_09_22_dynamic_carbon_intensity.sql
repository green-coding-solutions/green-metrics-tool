-- Migration: Add dynamic carbon intensity capabilities to existing users
-- Date: 2025-09-22
-- Description: Adds measurement.use_dynamic_carbon_intensity and measurement.carbon_intensity_location
--              to user updateable_settings and sets default values

-- Add new settings to updateable_settings for all users (excluding system user 0)
UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{user,updateable_settings}',
    (
        COALESCE(capabilities->'user'->'updateable_settings', '[]'::jsonb) ||
        '["measurement.use_dynamic_carbon_intensity", "measurement.carbon_intensity_location"]'::jsonb
    ),
    true
) WHERE id != 0;

-- Set default value for use_dynamic_carbon_intensity (disabled by default)
UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{measurement,use_dynamic_carbon_intensity}',
    'false',
    true
) WHERE id != 0;

-- Set default value for carbon_intensity_location (empty string, will be validated when dynamic is enabled)
UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{measurement,carbon_intensity_location}',
    '""',
    true
) WHERE id != 0;
