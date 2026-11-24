# Prebuilt GMT frontend image

`greencoding/gmt-frontend` is NGINX serving the static GMT frontend from `frontend/`.
It replaces the frontend part of the `green-coding-nginx` service from a regular install. The API, the database and the API proxy are not part of the image.

## Tags

- `latest` is the newest commit on `main`.
- `sha-<short commit>` exists for every commit on `main`.
- `v4.2` and so on exist for every release tag.

Many frontend tables read positional results from the API. Run the frontend from the same commit or release as your API. Mixing versions can break pages without an error.

## Configuration

The frontend reads its settings from `js/helpers/config.js`. You can provide it in two ways.

### Environment variables

On every start the container generates `config.js` from these variables.

| Variable | Default |
| --- | --- |
| `GMT_API_URL` | `http://api.green-coding.internal:9142` |
| `GMT_METRICS_URL` | `http://metrics.green-coding.internal:9142` |
| `GMT_ELEPHANT_URL` | empty |
| `GMT_ACTIVATE_SCENARIO_RUNNER` | `true` |
| `GMT_ACTIVATE_ECO_CI` | `false` |
| `GMT_ACTIVATE_CARBON_DB` | `false` |
| `GMT_ACTIVATE_POWER_HOG` | `false` |
| `GMT_ACTIVATE_SOFTWARE_VIEW` | `false` |
| `GMT_ACTIVATE_AI_OPTIMISATIONS` | `false` |

The `GMT_ACTIVATE_*` variables take `true` or `false` (also `1`/`0` and `yes`/`no`). An invalid value stops the container with an error.

```yaml
services:
  gmt-frontend:
    image: greencoding/gmt-frontend:latest
    restart: always
    ports:
      - 9142:9142
    environment:
      - GMT_API_URL=https://api.example.com
      - GMT_METRICS_URL=https://metrics.example.com
      - GMT_ACTIVATE_ECO_CI=true
      - GMT_ACTIVATE_CARBON_DB=true
```

### Mounted config.js

Mount your own file if you also want to change the chart settings in `config.js`, for example which metrics the Detailed Metrics view shows. Start from [`frontend/js/helpers/config.js.example`](../../frontend/js/helpers/config.js.example) or from the `config.js` of an existing install. The container serves a mounted file as it is and ignores the `GMT_*` variables.

```yaml
services:
  gmt-frontend:
    image: greencoding/gmt-frontend:latest
    restart: always
    ports:
      - 9142:9142
    volumes:
      - ./config.js:/var/www/green-metrics-tool/frontend/js/helpers/config.js:ro
```

## Things to set on the API side

- The API only answers browsers from origins in `cluster.cors_allowed_origins` in its `config.yml`. Add the URL the frontend is reachable under.
- `cluster.metrics_url` in the API `config.yml` should point to the frontend, as the backend uses it for links in emails and error reports.

## TLS

The container only listens on plain HTTP on port 9142. Put a reverse proxy with TLS in front of it, or mount your own NGINX config to `/etc/nginx/conf.d/default.conf`.

## Building and testing locally

From the repository root:

```bash
docker build -f docker/frontend-image/Dockerfile -t gmt-frontend:test .
./docker/frontend-image/test-image.sh gmt-frontend:test
```

The workflow `.github/workflows/build-and-push-frontend-image.yml` runs the same test on every pull request that touches the frontend. It pushes to Docker Hub for commits on `main` and for release tags.
