---
title: "Admin Deploy Verification"
summary: "How to verify that the Admin production build and nginx routing agree on the `/admin/` asset base path."
topics: [operations, deployment, frontend, routing]
sources:
  - id: agent-rules
    type: file
    path: AGENTS.md
  - id: playbook
    type: file
    path: .agents/knowledge/playbooks/admin-deploy-verifikation.md
  - id: admin-dockerfile
    type: file
    path: docker/Dockerfile.admin
  - id: admin-nginx
    type: file
    path: docker/nginx.admin.conf
  - id: admin-vite
    type: file
    path: frontend/admin/vite.config.ts
---

Use this guide after any change to the Admin Dockerfile, Admin nginx config, Vite base config, or after a deploy that could affect Admin asset routing. The failure mode is specific: the build can pass, but Admin loads a blank page because JavaScript and CSS assets were built for `/assets/` while the outer nginx expects the Admin app below `/admin/` [@agent-rules] [@playbook]. The successful outcome is a browser-verified Admin page whose JS and CSS requests return 200 from the intended Admin route.

## Check The Three Files Before Deploy

Start with `docker/Dockerfile.admin`. The production Admin build currently runs `VITE_BASE_PATH=/admin/ npm run build`, which embeds the `/admin/` base into the Vite output [@admin-dockerfile].

Then check `frontend/admin/vite.config.ts`. The Vite config reads `base` from `process.env.VITE_BASE_PATH` and falls back to `/`, so the Dockerfile's environment value is what makes the production build path differ from local Vite defaults [@admin-vite].

Finally check `docker/nginx.admin.conf`. The Admin container serves built files from `/usr/share/nginx/html`, returns real files under `/assets/`, proxies `/v1/` to the API, and falls back all other routes to `/index.html` [@admin-nginx]. The separate outer nginx route for `/admin/` is documented in [Ports And Routing](../../reference/operations/ports-and-routing); the key local invariant is that the outer route strips `/admin/` while the built HTML points asset URLs at `/admin/assets/...`.

## Deploy, Then Verify In Browser

After deploy, open the public Admin URL, for example:

```text
https://katalon.kraegelin.dev/admin/
```

Open DevTools Network and reload. JS and CSS requests must return 200, not 404, and they should resolve under the Admin asset path rather than the Portal path [@playbook]. This browser check is mandatory because the known failure does not produce a Docker build error [@agent-rules].

## Diagnose A Blank Admin Page

If Admin is blank after deployment, inspect network responses before editing code. A request for `/assets/...` on the outer host means the build probably missed `VITE_BASE_PATH=/admin/`; a request for `/admin/assets/...` returning 404 means nginx routing or path stripping is probably wrong [@agent-rules] [@admin-dockerfile].

When fixing, keep the build-time Vite base, Admin container nginx routes, and outer nginx `/admin/` route consistent as one change. For deployment customization policy, use [Docker Customization Strategy](../../decisions/operations/docker-customization-strategy) instead of changing base paths ad hoc.
