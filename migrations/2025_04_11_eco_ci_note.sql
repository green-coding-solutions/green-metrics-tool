ALTER TABLE "public"."ci_measurements" ADD COLUMN your_column_name TEXT CHECK (LENGTH("note") <= 1024);
