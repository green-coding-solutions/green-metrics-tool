ALTER TABLE "public"."ci_measurements" ADD COLUMN "note" TEXT CHECK (LENGTH("note") <= 1024);
