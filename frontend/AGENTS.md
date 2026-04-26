# Frontend Agent Guide

The frontend is a static HTML + vanilla JavaScript application served by NGINX.

## Structure

- Top-level `*.html`
  - Individual pages such as `runs.html`, `stats.html`, `compare.html`, `request.html`, `watchlist.html`
- `js/`
  - Page-specific logic
- `js/helpers/`
  - Shared API, formatting, chart, phase-stat, and config helpers
- `css/green-coding.css`
  - Project-owned styling
- `dist/`
  - Third-party built assets; avoid editing unless the task is explicitly vendor-related

## Working rules

- Keep configuration in `js/helpers/config.js` and `config.js.example`; do not hard-code environment URLs into page scripts.
- Most pages map directly to a page-specific script. Check both the HTML and its corresponding JS before changing behavior.
- Several tables consume positional arrays returned by API SQL queries. Backend column order changes often require frontend updates.
- Shared menu, notifications, and API helpers live in `js/helpers/main.js`.
- Preserve the existing vanilla JS style unless the repository already establishes a different pattern in the files you touch.
