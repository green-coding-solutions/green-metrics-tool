UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    (capabilities #> '{api,routes}')::jsonb || '["/v1/watchlist""]',
    true -- Create the key if it doesn't exist
)

ALTER TABLE "public"."timeline_projects" RENAME TO "watchlist";
ALTER INDEX public."timeline_projects_pkey" RENAME TO "watchlist_pkey";
