CREATE TABLE client_status (
    id SERIAL PRIMARY KEY,
	status_code TEXT NOT NULL,
	machine_id int REFERENCES machines(id) ON DELETE SET NULL ON UPDATE CASCADE DEFAULT null,
	"data" TEXT,
	project_id uuid REFERENCES projects(id) ON DELETE CASCADE ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now()
);