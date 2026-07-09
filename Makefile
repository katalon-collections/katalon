# Katalon – Build & Deploy Makefile
# Usage: make <target>  (run `make help` for all commands)

.PHONY: help build build-api build-worker build-admin build-portal rebuild \
        rebuild-api rebuild-worker rebuild-admin rebuild-portal \
        up up-dev down down-volumes clean clean-all knowledge-site

# Compose command — override with: COMPOSE="docker-compose" make up
COMPOSE ?= docker compose

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
help:
	@echo "Katalon – Build & Deploy Commands"
	@echo ""
	@echo "Build (with Docker layer cache for speed):"
	@echo "  make build          Build all Katalon services"
	@echo "  make build-api      Build API service only"
	@echo "  make build-worker   Build Worker service only"
	@echo "  make build-admin    Build Admin frontend only"
	@echo "  make build-portal   Build Portal frontend only"
	@echo ""
	@echo "Rebuild (no cache → fresh build + cleanup old images):"
	@echo "  make rebuild        Rebuild all services + prune dangling images/cache"
	@echo "  make rebuild-api    Rebuild API + Worker + prune"
	@echo "  make rebuild-admin  Rebuild Admin + prune"
	@echo "  make rebuild-portal Rebuild Portal + prune"
	@echo ""
	@echo "Deploy:"
	@echo "  make up             Start full stack (docker compose up -d --build)"
	@echo "  make up-dev         Start dev infrastructure (DB, Redis, ES, Cantaloupe)"
	@echo "  make down           Stop stack"
	@echo "  make down-volumes   Stop stack and remove volumes"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          Remove dangling images and build cache"
	@echo "  make clean-all      Full docker system prune (images, containers, cache, volumes)"
	@echo ""
	@echo "Dev knowledge:"
	@echo "  make knowledge-site Render .agents/knowledge/ (OKF bundle) to a local static site"

# ---------------------------------------------------------------------------
# Build (with cache)
# ---------------------------------------------------------------------------
build:
	$(COMPOSE) build api worker admin portal

build-api:
	$(COMPOSE) build api

build-worker:
	$(COMPOSE) build worker

build-admin:
	$(COMPOSE) build admin

build-portal:
	$(COMPOSE) build portal

# ---------------------------------------------------------------------------
# Rebuild (no cache + cleanup)
# ---------------------------------------------------------------------------
rebuild:
	$(COMPOSE) build --no-cache api worker admin portal
	$(MAKE) clean

rebuild-api:
	$(COMPOSE) build --no-cache api worker
	$(MAKE) clean

rebuild-admin:
	$(COMPOSE) build --no-cache admin
	$(MAKE) clean

rebuild-portal:
	$(COMPOSE) build --no-cache portal
	$(MAKE) clean

# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------
up:
	$(COMPOSE) up -d --build

up-dev:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml up -d db redis elasticsearch cantaloupe

down:
	$(COMPOSE) down --remove-orphans

down-volumes:
	$(COMPOSE) down -v --remove-orphans

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
clean:
	@echo "==> Removing dangling images and build cache..."
	-docker image prune -f
	-docker builder prune -f
	@echo "==> Done."

clean-all: down-volumes
	@echo "==> Full system prune (containers, images, cache, volumes)..."
	-docker system prune -f --volumes
	@echo "==> Done."

# ---------------------------------------------------------------------------
# Dev knowledge (OKF bundle)
# ---------------------------------------------------------------------------
knowledge-site:
	uv run .agents/tools/okf_site.py .agents/knowledge .agents/knowledge/_site
	@echo "Open .agents/knowledge/_site/index.html"
