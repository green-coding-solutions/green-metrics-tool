# Thank you, FOSS

Green Metrics Tool is built on the shoulders of open-source projects. This page is a shout-out to libraries, tools, and platforms we rely on. It is not exhaustive—if something is missing, please open a PR.

## Operating systems

GMT runs on and is often packaged with Linux distributions including **Alpine**, **Ubuntu**, and **Fedora**.

## Runtime & infrastructure

| Project | Role |
|---------|------|
| [Python](https://www.python.org/) | Core backend and metric tooling |
| [Docker](https://www.docker.com/) / [Moby](https://mobyproject.org/) | Scenario orchestration and isolation |
| [PostgreSQL](https://www.postgresql.org/) | Primary data store |
| [Redis](https://redis.io/) | Caching / coordination where used |
| [NGINX](https://nginx.org/) | Frontend and reverse proxy |
| [Gunicorn](https://gunicorn.org/) | WSGI application server |
| [Squid](http://www.squid-cache.org/) | Proxy support in measurement environments |
| [tcpdump](https://www.tcpdump.org/) | Packet capture for network-related metrics |

## Frontend

| Project | Role |
|---------|------|
| [ECharts](https://echarts.apache.org/) | Charts and timelines |
| [jQuery](https://jquery.com/) | DOM helpers (legacy UI paths) |
| [Fomantic UI](https://fomantic-ui.com/) / Semantic UI styles | Layout and components |
| [DataTables](https://datatables.net/) | Tabular views |
| [diff2html](https://diff2html.rtfpessoa.xyz/) | Diff rendering |
| [jquery-tablesort](https://github.com/tristen/tablesort) | Table sorting helpers |
| [json2yaml](https://github.com/jeffsoy/json2yaml) | JSON ↔ YAML utilities in the UI tooling path |

## Python packages

Pinned application and development dependencies live in the repository requirement files rather than being listed one-by-one here:

- `requirements.txt`
- `docker/requirements.txt`
- `requirements-dev.txt`

Thanks to every package maintainer represented in those files.

## Docs & project tooling

| Project | Role |
|---------|------|
| [Hugo](https://gohugo.io/) | Project documentation site (docs.green-coding.io) |
| [Doks](https://getdoks.org/) | Documentation theme (Doks / Hugo docs template used by the site) |
| [Git](https://git-scm.com/) / [GitHub Actions](https://github.com/features/actions) | Version control and CI |

## Testing

| Project | Role |
|---------|------|
| [pytest](https://pytest.org/) | Python test runner |
| [Playwright](https://playwright.dev/) | Frontend / browser tests |
| [pylint](https://pylint.pycqa.org/) | Python static analysis |

## Standards & protocols

We also depend on open specifications such as Linux power interfaces (e.g. RAPL), IPMI where applicable, and the broader container ecosystem.
