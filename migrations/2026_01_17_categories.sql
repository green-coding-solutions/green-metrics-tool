ALTER TABLE "runs" RENAME COLUMN "categories" TO "category_ids";
ALTER TABLE "jobs" RENAME COLUMN "categories" TO "category_ids";
ALTER TABLE "watchlist" RENAME COLUMN "categories" TO "category_ids";


-- --------------------------------------------------

-- Trigger function to validate category array elements are present in reference table
--
-- We decided for putting this trigger into the DB to guarantee internal consistency.
-- Although we also check on insertion as a job if the ID exists to provider nicer errors this DB check
-- guarantees that even if an admin fiddles with the DB the data is consistent
CREATE OR REPLACE FUNCTION validate_category_ids()
RETURNS TRIGGER AS $$
DECLARE
    invalid_ids INT[];
BEGIN
    SELECT ARRAY_AGG(cid)
    INTO invalid_ids
    FROM unnest(NEW.category_ids) AS cid
    LEFT JOIN categories c ON c.id = cid
    WHERE c.id IS NULL;

    IF invalid_ids IS NOT NULL THEN
        RAISE EXCEPTION 'At least one category ID supplied (%) does not exist as category. Please check if category is a typo otherwise add category first', invalid_ids;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger before insert or update
CREATE TRIGGER trg_validate_category_ids
BEFORE INSERT OR UPDATE ON runs
FOR EACH ROW EXECUTE FUNCTION validate_category_ids();

-- Trigger before insert or update
CREATE TRIGGER trg_validate_category_ids
BEFORE INSERT OR UPDATE ON jobs
FOR EACH ROW EXECUTE FUNCTION validate_category_ids();
-- Trigger before insert or update
CREATE TRIGGER trg_validate_category_ids
BEFORE INSERT OR UPDATE ON watchlist
FOR EACH ROW EXECUTE FUNCTION validate_category_ids();


