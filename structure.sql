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
    mem bigint,
    mem_max bigint,
    net_in bigint,
    net_out bigint,
    time integer,
    created_at timestamp with time zone DEFAULT now()
);
