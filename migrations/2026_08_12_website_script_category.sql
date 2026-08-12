-- Category for website measurements that run a user supplied Playwright path
-- (submitted through https://website-tester.green-coding.io via gateway.green-coding.io)
--
-- The id is generated, so read it back after applying and put it into the CATEGORY_ID_WEBSITE_SCRIPT
-- constant of the cloudflare worker in gateway.green-coding.io:
--     SELECT id FROM categories WHERE name = 'website_script';
INSERT INTO categories (name, parent_id) VALUES ('website_script', NULL);
