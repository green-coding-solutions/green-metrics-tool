CREATE TABLE hello_data (
    id SERIAL PRIMARY KEY,
    hash text,
    os text,
    created_at timestamp with time zone DEFAULT now(),
);
