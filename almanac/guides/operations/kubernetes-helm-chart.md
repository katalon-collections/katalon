---
title: "Kubernetes Helm Chart (Starter, Bring-Your-Own-Ops)"
summary: "What the charts/katalon Helm chart covers, how it maps to docker-compose.yml, and the known pitfalls before running real traffic through it."
topics: [operations, deployment, kubernetes]
sources:
  - id: agents
    type: file
    path: AGENTS.md
  - id: chart
    type: file
    path: charts/katalon/Chart.yaml
  - id: chart-values
    type: file
    path: charts/katalon/values.yaml
  - id: chart-api
    type: file
    path: charts/katalon/templates/api.yaml
  - id: chart-cantaloupe
    type: file
    path: charts/katalon/templates/cantaloupe.yaml
  - id: chart-ingress
    type: file
    path: charts/katalon/templates/ingress.yaml
  - id: chart-notes
    type: file
    path: charts/katalon/templates/NOTES.txt
  - id: compose
    type: file
    path: docker-compose.yml
  - id: nginx-conf
    type: file
    path: docker/nginx.conf
  - id: media-api
    type: file
    path: backend/src/katalon/api/v1/media.py
---

`charts/katalon/` is a proof-of-concept Helm chart, not the production deployment path [@chart]. Katalon's fixed deployment architecture is Docker Compose, distributed via `katalon-cli` [@agents]. This chart exists so an operator with their own Kubernetes expertise has a starting point, not a supported alternative — see [Production Deployment](production-deployment) for the actual production path.

## Service Mapping

The chart mirrors `docker-compose.yml` service-for-service: `db` (Postgres, StatefulSet+PVC), `redis` (Deployment), `elasticsearch` (StatefulSet+PVC), `cantaloupe` (Deployment+PVC), `api` (Deployment, with an `alembic upgrade head` initContainer instead of compose's manual migration step), `worker`, `beat`, `admin`, `portal` (Deployments), and two `Ingress` objects replacing the outer `nginx` container's path routing (`/api/`, `/v1/`, `/portal/v1/`, `/oai`, `/iiif/`, `/`, plus a separate admin Ingress for `/admin/`) [@compose] [@chart-api] [@chart-ingress] [@nginx-conf]. The admin Ingress exists because the outer nginx strips the `/admin/` prefix before proxying to the admin container; without the equivalent `rewrite-target` (nginx-ingress annotation), `/admin/assets/*` falls into the admin SPA fallback and the UI loads blank [@chart-ingress] [@nginx-conf]. The `backup` sidecar from compose has no equivalent — see Known Gaps below.

Images are referenced by repo/tag from `values.image.registry`; the chart does not build them. Build and push `katalon-backend`, `katalon-worker`, `katalon-admin`, `katalon-portal` from `docker/Dockerfile.*` before installing [@chart-values].

## Known Pitfalls

**One release per namespace.** The admin and portal images hardcode `proxy_pass http://api:8000` in their own nginx config, and nginx refuses to start if `api` doesn't resolve. The chart therefore creates an extra Service literally named `api` next to `{{ .Release.Name }}-api` [@chart-api]; a second release in the same namespace would collide on it.

**Required values.** `secrets.defaultAdminPassword` is required (`helm install` fails without it): it is passed to the api as `INITIAL_ADMIN_PASSWORD`, the password of the first admin (a well-known default is replaced by a random one when `KATALON_BASE_URL` is set). `image.tag` in `values.yaml` is a stale placeholder — always pass the tag of the images you built [@chart-values].

**IIIF auth gate needs ingress-nginx.** Cantaloupe has no authorization of its own; the Compose stack gates `/iiif/` with an nginx `auth_request` [@nginx-conf]. The chart mirrors this with a separate `/iiif/` Ingress carrying `nginx.ingress.kubernetes.io/auth-url` pointing at the same `GET /v1/media/_authorize` endpoint [@chart-ingress]. ingress-nginx sends the original request as `X-Original-URL` (full URL) rather than `X-Original-URI`, so the endpoint falls back to the path of `X-Original-URL` when `X-Original-URI` is absent [@media-api]. Other ingress controllers (Traefik, Gateway API) ignore the annotation and leave `/iiif/` open — recreate the gate with their own forward-auth mechanism before serving non-public media. Verified on minikube: public image 200 anonymous, private image 403 anonymous / 200 with bearer token.

**Migration timing.** Migrations run as an `api` Deployment initContainer (`wait-for-db` then `alembic upgrade head`) rather than a Helm pre-install hook, because pre-install hooks fire before any chart-managed resource — including the `db` StatefulSet — exists, which would make a hook-based migration job fail DNS resolution on first install [@chart-api].

**Media storage must be RWX for multi-pod api/worker/cantaloupe.** All three mount the same `{{ .Release.Name }}-media` PVC. On a single-node cluster (OrbStack, kind, k3d) RWO is fine since every pod lands on the same node; on a multi-node cluster, the StorageClass backing `cantaloupe.storageClassName` must support `ReadWriteMany` (NFS, EFS, Longhorn, etc.) or multi-replica `api`/`worker`/`cantaloupe` pods will fail to schedule [@chart-cantaloupe].

**Cantaloupe is the first bottleneck under load, not the API.** IIIF tile/thumbnail delivery is CPU- and IO-heavy; a viewer page can issue a dozen+ tile requests. The chart deploys Cantaloupe as a single Deployment with `replicas` hardcoded to `1` in the template (not exposed via `values.yaml`) [@chart-cantaloupe]. Scaling Cantaloupe requires both raising that replica count (currently a template edit, not a values knob) and adding a cache layer in front of it (CDN or ingress-level caching) so repeated tile requests aren't re-rendered per request.

**No HA on stateful components.** `db` and `elasticsearch` run as single-replica StatefulSets [@chart-cantaloupe]. Fine for demo/staging traffic; for production HA, swap in a proper operator or subchart (e.g. `bitnami/postgresql`, an Elasticsearch/OpenSearch operator) rather than scaling these templates directly.

**No backup job, autoscaling, PodDisruptionBudget, or NetworkPolicy.** None of these are wired up; see `charts/katalon/templates/NOTES.txt`, which is printed after every `helm install`/`upgrade` as a live reminder of these gaps [@chart-notes].

## Scaling What Already Works

`api`, `admin`, `portal`, and `worker` are stateless and already take a replica count from `values.yaml` (`api.replicas`, `admin.replicas`, `portal.replicas`, `worker.replicas`) [@chart-values]:

```bash
helm upgrade katalon charts/katalon --reuse-values \
  --set api.replicas=3 --set admin.replicas=2 --set portal.replicas=2 --set worker.replicas=3
```

For a rough sense of scale: ~200k requests/day averages to ~2.3 req/s, with bursts well within what a few `api` replicas handle. At that volume the constraint is image delivery (Cantaloupe), not the API tier — see the Cantaloupe pitfall above before assuming replica count alone solves throughput.

## Local Verification

Use a local cluster (OrbStack's Kubernetes, or minikube with `--driver=docker`), not a real cluster context — check `kubectl config current-context` before installing anything. On Linux with minikube, an active Cisco AnyConnect VPN blocks host → container-IP traffic, so `minikube start` hangs on SSH handshake resets; disconnect the VPN first. Images can be built with the host Docker (`docker build -t katalon-backend:<tag> -f docker/Dockerfile.backend .`, worker with context `backend/`) and pushed into the node with `minikube image load`; install with `--set ingress.className=nginx` after `minikube addons enable ingress`. `helm lint charts/katalon` and `helm template katalon charts/katalon` both run clean and are the fast sanity checks before an actual `helm install`.
