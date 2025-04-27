ALTER TABLE "public"."watchlist" RENAME COLUMN "url" TO "repo_url";
ALTER TABLE "public"."watchlist" ADD COLUMN "image_url" text;
