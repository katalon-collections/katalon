# Vendored API docs assets

Self-hosted so `/api/docs` and `/api/redoc` work under the strict
`script-src 'self'` CSP (see `docker/nginx*.conf`) without loading from a
third-party CDN or relying on inline `<script>` blocks.

| File                    | Package             | Version | License |
|--------------------------|----------------------|---------|---------|
| `swagger-ui-bundle.js`   | swagger-ui-dist       | 5.33.0  | Apache-2.0 |
| `swagger-ui.css`         | swagger-ui-dist       | 5.33.0  | Apache-2.0 |
| `redoc.standalone.js`    | redoc                 | 2.5.4   | MIT |
| `swagger-ui-init.js`     | hand-written (this repo) | —   | AGPL-3.0-or-later |

To update: bump the version in the jsdelivr URL below, re-download, and
update this table.

```
curl -sL https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js -o swagger-ui-bundle.js
curl -sL https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css -o swagger-ui.css
curl -sL https://cdn.jsdelivr.net/npm/redoc@2/bundles/redoc.standalone.js -o redoc.standalone.js
```
