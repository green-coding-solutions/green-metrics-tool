CREATE TABLE projects (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    name text,
    url text,
    email text,
    crawled boolean DEFAULT false,
    last_crawl timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE stats (
    id SERIAL PRIMARY KEY,
    project_id uuid REFERENCES projects(id),
    container_name text,
    cpu integer,
    mem integer,
    mem_max integer,
    net_in integer,
    net_out integer,
    time integer,
    created_at timestamp with time zone DEFAULT now()
);
