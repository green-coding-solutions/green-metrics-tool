ALTER TABLE users
ADD COLUMN IF NOT EXISTS ssh_private_key text;
