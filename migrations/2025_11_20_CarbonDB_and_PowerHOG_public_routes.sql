-- Add new routes to allow list
UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    (capabilities #> '{api,routes}')::jsonb || '["/v1/carbondb/insights","/v1/hog/insights","/v2/carbondb/add","/v2/carbondb","/v2/carbondb/filters","/v2/hog/add","/v2/hog/top_processes","/v2/hog/details"]',
    true -- Create the key if it doesn't exist
)
WHERE id = 1;


