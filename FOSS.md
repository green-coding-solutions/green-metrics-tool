# Thank you, FOSS

Green Metrics Tool is built on the shoulders of open-source projects. This page is a shout-out to libraries, tools, and platforms we rely on. It is not exhaustive—if something is missing, please open a PR.

## Runtime & language

| Project | Role |
|---------|------|
| [Python](https://www.python.org/) | Core backend and metric tooling |
| [Docker](https://www.docker.com/) / [Moby](https://mobyproject.org/) | Scenario orchestration and isolation |
| [PostgreSQL](https://www.postgresql.org/) | Primary data store |
| [Redis](https://redis.io/) | Caching / coordination where used |
| [NGINX](https://nginx.org/) | Frontend and reverse proxy |
| [Gunicorn](https://gunicorn.org/) | WSGI application server |

## Frontend

| Project | Role |
|---------|------|
| [ECharts](https://echarts.apache.org/) | Charts and timelines |
| [jQuery](https://jquery.com/) | DOM helpers (legacy UI paths) |
| [Fomantic UI](https://fomantic-ui.com/) / Semantic UI styles | Layout and components |
| [DataTables](https://datatables.net/) | Tabular views |

## Python ecosystem (examples)

Packages evolve with `requirements` / install scripts; commonly involved areas include HTTP APIs, DB drivers, YAML/JSON tooling, and scientific utilities used by metric providers. See the repository dependency files and container definitions for the exact pinned set on a given release.

## Docs & project tooling

| Project | Role |
|---------|------|
| [Hugo](https://gohugo.io/) | Project documentation site (docs.green-coding.io) |
| [Git](https://git-scm.com/) / [GitHub Actions](https://github.com/features/actions) | Version control and CI |

## Standards & protocols

We also depend on open specifications such as Linux power interfaces (e.g. RAPL), IPMI where applicable, and the broader container ecosystem.

---

*Maintained as a living thank-you note ([#953](https://github.com/green-coding-solutions/green-metrics-tool/issues/953)).*
