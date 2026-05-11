#!/usr/bin/env bash
set -e

# ---------------------------------------------------------------------------
# Katalon – Easy Installer
#
# Usage:
#   ./install.sh --help       – Diese Hilfe anzeigen
#   ./install.sh --up         – Dependencies checken, .env erstellen, Stack starten
#   ./install.sh --up --demo  – Wie oben + ICS-Demo-Daten seeden
#   ./install.sh --reset      – Datenbank & Volumes löschen, Stack frisch starten
#   ./install.sh --reset --demo  – Komplettreset + Demo-Daten
#   ./install.sh --dev        – Nur Infra-Services (DB, Redis, ES, Cantaloupe)
#   ./install.sh --down       – Stack herunterfahren
#   ./install.sh --down -v    – Stack herunterfahren und Volumes löschen
# ---------------------------------------------------------------------------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}ℹ${NC}  $*"; }
ok()    { echo -e "${GREEN}✔${NC}  $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
err()   { echo -e "${RED}✖${NC}  $*" >&2; }

# --- Argumente parsen ------------------------------------------------------

UP=false
DEMO=false
RESET=false
DEV=false
DOWN=false
DOWN_VOLUMES=false
ENV_CREATED=false

show_help() {
    echo "Usage: $0 [--up] [--demo] [--reset] [--dev] [--down] [--down -v] [--help]"
    echo ""
    echo "  --up          Stack bauen und starten (Standard-Aktion, wenn kein anderes Kommando gesetzt ist)"
    echo "  --demo        Demo-Daten (ICS-Spielesammlung) nach dem Start einspielen"
    echo "  --reset       Bestehende Docker-Volumes löschen und frisch starten"
    echo "  --dev         Nur Infra-Services starten (DB, Redis, ES, Cantaloupe)"
    echo "                für lokale Entwicklung mit Hot-Reload"
    echo "  --down        Stack herunterfahren"
    echo "  --down -v     Stack herunterfahren und Docker-Volumes löschen"
    echo "  --help, -h    Diese Hilfe anzeigen"
}

ensure_katalon_base_url() {
    local current_base_url
    current_base_url=$(grep '^KATALON_BASE_URL=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' | xargs || true)

    if [[ -n "$current_base_url" ]]; then
        ok "KATALON_BASE_URL gesetzt: $current_base_url"
        return
    fi

    warn "KATALON_BASE_URL ist in .env nicht gesetzt."
    warn "Diese URL wird für den ersten Admin-Account benötigt (z.B. https://katalon.example.org)."

    while true; do
        read -rp "Bitte KATALON_BASE_URL eingeben: " current_base_url
        current_base_url=$(echo "$current_base_url" | xargs)
        if [[ "$current_base_url" =~ ^https?://[A-Za-z0-9.-]+(:[0-9]+)?$ ]]; then
            break
        fi
        warn "Ungültige URL. Bitte mit http:// oder https:// beginnen."
    done

    if grep -q '^KATALON_BASE_URL=' .env; then
        sed -i "s|^KATALON_BASE_URL=.*|KATALON_BASE_URL=$current_base_url|" .env
    else
        echo "KATALON_BASE_URL=$current_base_url" >> .env
    fi

    ok "KATALON_BASE_URL wurde in .env gespeichert."
}

show_first_run_credentials() {
    if [[ "$API_READY" == false ]]; then
        return
    fi

    info "Prüfe API-Logs auf First-Run-Zugangsdaten …"

    for i in $(seq 1 30); do
        local api_logs
        api_logs=$($COMPOSE_CMD logs api --no-color --tail=100 2>/dev/null || true)
        if echo "$api_logs" | grep -q "====== KATALON FIRST RUN ======"; then
            echo
            echo "$api_logs" | sed -n '/====== KATALON FIRST RUN ======/,/================================/p'
            echo

            local api_container
            api_container=$($COMPOSE_CMD ps -q api | head -n1)
            if [[ -n "$api_container" ]]; then
                if docker cp "$api_container:/var/lib/katalon/first-run-credentials.txt" "./first-run-credentials.txt" >/dev/null 2>&1; then
                    ok "First-Run-Credentials wurden nach ./first-run-credentials.txt kopiert."
                else
                    warn "Konnte /var/lib/katalon/first-run-credentials.txt nicht per docker cp abrufen."
                fi
            fi
            return
        fi
        sleep 2
    done

    info "Kein First-Run-Block gefunden (vermutlich bereits initialisiert)."
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --up)
            UP=true
            shift
            ;;
        --demo)
            DEMO=true
            shift
            ;;
        --reset)
            RESET=true
            shift
            ;;
        --dev)
            DEV=true
            shift
            ;;
        --down)
            DOWN=true
            shift
            ;;
        -v)
            DOWN_VOLUMES=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            err "Unbekanntes Argument: $1"
            show_help
            exit 1
            ;;
    esac
done

# Ohne Argumente Hilfe anzeigen
if [[ "$UP" == false && "$DEMO" == false && "$RESET" == false && "$DEV" == false && "$DOWN" == false ]]; then
    show_help
    exit 0
fi

if [[ "$DEV" == true && "$DEMO" == true ]]; then
    err "--demo kann nicht mit --dev kombiniert werden (im Dev-Modus läuft die API lokal)."
    exit 1
fi

if [[ "$DOWN" == true ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$SCRIPT_DIR"

    # Compose-Command ermitteln (wie später im Script)
    if docker compose version &>/dev/null; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &>/dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        err "Docker Compose ist nicht installiert."
        exit 1
    fi

    if [[ "$DOWN_VOLUMES" == true ]]; then
        warn "Stack wird heruntergefahren und Volumes werden gelöscht …"
        $COMPOSE_CMD down -v --remove-orphans
        ok "Stack und Volumes wurden entfernt."
    else
        info "Fahre Stack herunter …"
        $COMPOSE_CMD down --remove-orphans
        ok "Stack wurde heruntergefahren."
    fi
    exit 0
fi

info "Katalon Installer gestartet …"
echo

# --- 1. Docker prüfen ------------------------------------------------------

if ! command -v docker &>/dev/null; then
    err "Docker ist nicht installiert oder nicht im PATH."
    err "   → https://docs.docker.com/get-docker/"
    exit 1
fi

DOCKER_VERSION=$(docker --version 2>/dev/null | awk '{print $3}' | tr -d ',')
ok "Docker gefunden: $DOCKER_VERSION"

# --- 2. Docker Compose prüfen ----------------------------------------------

if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
    COMPOSE_VERSION=$(docker compose version --short 2>/dev/null)
    ok "Docker Compose (Plugin) gefunden: $COMPOSE_VERSION"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
    COMPOSE_VERSION=$(docker-compose --version 2>/dev/null | awk '{print $3}' | tr -d ',')
    ok "Docker Compose (Standalone) gefunden: $COMPOSE_VERSION"
else
    err "Docker Compose ist nicht installiert."
    err "   → https://docs.docker.com/compose/install/"
    exit 1
fi

# --- 3. Optional: uv prüfen (nur für Local-Dev relevant) -------------------

if command -v uv &>/dev/null; then
    UV_VERSION=$(uv --version 2>/dev/null | awk '{print $2}')
    ok "uv gefunden: $UV_VERSION (für Local-Dev optional)"
else
    warn "uv nicht gefunden. Für Local-Development wird uv empfohlen:"
    warn "   → https://github.com/astral-sh/uv#installation"
fi

echo

# --- 4. Pfade ermitteln ----------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- 5. Reset (optional) ---------------------------------------------------

if [[ "$RESET" == true ]]; then
    warn "Reset angefordert – bestehende Container und Volumes werden gelöscht!"
    read -rp "Möchtest du wirklich alle Daten zurücksetzen? [j/N] " confirm
    if [[ ! "$confirm" =~ ^[Jj] ]]; then
        info "Abgebrochen."
        exit 0
    fi

    info "Fahre Stack herunter und entferne Volumes …"
    $COMPOSE_CMD down -v --remove-orphans
    ok "Volumes und Container wurden entfernt."
    echo
fi

# --- 6. .env prüfen / erstellen --------------------------------------------

if [[ -f .env ]]; then
    ok ".env existiert bereits."
else
    if [[ -f .env.example ]]; then
        warn ".env fehlt – wird aus .env.example erstellt."
        cp .env.example .env
        ENV_CREATED=true
        ok ".env wurde erstellt."
        warn "Bitte öffne .env und passe mindestens folgende Werte an:"
        echo "   • POSTGRES_PASSWORD"
        echo "   • DATABASE_URL       (muss zum Passwort passen)"
        echo "   • SECRET_KEY"
        echo "   • KATALON_BASE_URL"
        echo
        read -rp "Möchtest du jetzt fortfahren (die Standardwerte aus .env.example werden verwendet)? [j/N] " answer
        if [[ ! "$answer" =~ ^[Jj] ]]; then
            info "Installation abgebrochen. Bearbeite .env und starte das Script erneut."
            exit 0
        fi
    else
        err ".env.example nicht gefunden. Kann .env nicht automatisch erstellen."
        exit 1
    fi
fi

echo

if [[ "$DEV" == false ]]; then
    ensure_katalon_base_url
    echo
fi

# ═══════════════════════════════════════════════════════════════════════════
# DEV-MODUS  –  Nur Infra-Services
# ═══════════════════════════════════════════════════════════════════════════

if [[ "$DEV" == true ]]; then
    info "Starte Infra-Services für Local Development …"
    echo

    $COMPOSE_CMD up -d db redis elasticsearch cantaloupe

    ok "Infra-Services laufen."
    echo

    info "Warte auf Datenbank-Healthcheck (max. 60 Sekunden) …"
    DB_READY=false
    for i in $(seq 1 30); do
        if $COMPOSE_CMD exec db pg_isready -U katalon >/dev/null 2>&1; then
            DB_READY=true
            ok "PostgreSQL ist bereit."
            break
        fi
        sleep 2
    done

    if [[ "$DB_READY" == false ]]; then
        warn "PostgreSQL scheint nicht bereit zu sein. Prüfe die Logs:"
        warn "   $COMPOSE_CMD logs db -f"
        echo
    fi

    echo
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           Dev-Infra bereit – Los geht's!                      ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo
    info "Lokale Services starten (jeder in einem eigenen Terminal):"
    echo
    echo "── 1. Python-Umgebung vorbereiten (einmalig) ────────────────────────"
    echo "   cd backend"
    echo "   uv venv              # Virtualenv erstellen"
    echo "   source .venv/bin/activate"
    echo "   uv pip install -e .  # Dependencies installieren"
    echo
    echo "── 2. API-Server starten (Hot-Reload) ───────────────────────────────"
    echo "   cd backend"
    echo "   source .venv/bin/activate"
    echo "   uvicorn katalon.main:app --reload --port 8000"
    echo
    echo "── 3. Admin-Frontend starten (Hot-Reload) ───────────────────────────"
    echo "   cd frontend/admin"
    echo "   npm install          # einmalig"
    echo "   npm run dev"
    echo
    echo "── 4. Portal-Frontend starten (Hot-Reload) ──────────────────────────"
    echo "   cd frontend/portal"
    echo "   npm install          # einmalig"
    echo "   npm run dev"
    echo
    info "Zugriff im Dev-Modus:"
    echo "   • Admin UI        → http://localhost:5173"
    echo "   • Portal UI       → http://localhost:5174  (oder was Vite anzeigt)"
    echo "   • API Docs        → http://localhost:8000/api/docs"
    echo "   • API Health      → http://localhost:8000/health"
    echo
    info "Infra-Services stoppen:"
    echo "   $COMPOSE_CMD down"
    echo "   $COMPOSE_CMD down -v   # inkl. Datenbank zurücksetzen"
    echo
    exit 0
fi

# ═══════════════════════════════════════════════════════════════════════════
# PRODUCTION / FULL-STACK-MODUS
# ═══════════════════════════════════════════════════════════════════════════

# --- 7. Docker Compose Stack starten ---------------------------------------

info "Baue und starte den Katalon-Stack …"
echo

$COMPOSE_CMD up -d --build

echo
ok "Stack wurde gestartet."
echo

# --- 8. Warten bis API bereit ist ------------------------------------------

info "Warte auf API-Healthcheck (max. 120 Sekunden) …"

API_READY=false
for i in $(seq 1 60); do
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        API_READY=true
        ok "API ist bereit (http://localhost:8000/health)"
        break
    fi
    sleep 2
done

if [[ "$API_READY" == false ]]; then
    warn "API scheint nicht bereit zu sein. Prüfe die Logs:"
    warn "   $COMPOSE_CMD logs api -f"
    echo
fi

show_first_run_credentials

# --- 9. Demo-Daten seeden (optional) ---------------------------------------

if [[ "$DEMO" == true ]]; then
    if [[ "$API_READY" == false ]]; then
        err "API nicht erreichbar – Demo-Daten können nicht eingespielt werden."
        exit 1
    fi

    info "Spiele Demo-Daten ein …"
    echo

    API_CONTAINER=$($COMPOSE_CMD ps -q api | head -n1)
    if [[ -z "$API_CONTAINER" ]]; then
        err "API-Container nicht gefunden."
        exit 1
    fi

    SEED_SCRIPT="backend/scripts/seed_ics_demo.py"
    if [[ ! -f "$SEED_SCRIPT" ]]; then
        err "Seed-Script nicht gefunden: $SEED_SCRIPT"
        exit 1
    fi

    # Lese Admin-Zugangsdaten aus .env (mit Fallback auf Seeder-Defaults)
    SEED_EMAIL=$(grep '^DEFAULT_ADMIN_EMAIL=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
    SEED_PASSWORD=$(grep '^DEFAULT_ADMIN_PASSWORD=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
    SEED_EMAIL=${SEED_EMAIL:-admin@katalon.dev}
    SEED_PASSWORD=${SEED_PASSWORD:-admin}

    # Kopiere Script in den Container und führe es aus
    docker cp "$SEED_SCRIPT" "$API_CONTAINER:/tmp/seed_ics_demo.py"
    docker exec "$API_CONTAINER" \
        python /tmp/seed_ics_demo.py \
        --base-url http://localhost:8000 \
        --email "$SEED_EMAIL" \
        --password "$SEED_PASSWORD"

    ok "Demo-Daten wurden eingespielt."
    echo
fi

# --- 10. Zusammenfassung ---------------------------------------------------

echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                 Katalon ist bereit                            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo
info "Oberflächen:"
echo "   • Admin UI        → http://localhost:3000"
echo "   • Portal UI       → http://localhost:3001"
echo "   • Nginx Proxy     → http://localhost"
echo
info "API & Docs:"
echo "   • API Base        → http://localhost:8000"
echo "   • Swagger UI      → http://localhost:8000/api/docs"
echo "   • Health Check    → http://localhost:8000/health"
echo
if [[ "$DEMO" == true ]]; then
    info "Demo-Zugangsdaten:"
    echo "   • E-Mail          → admin@katalon.dev"
    echo "   • Passwort        → admin"
    echo
fi
info "Hilfreiche Befehle:"
echo "   • Logs ansehen    → $COMPOSE_CMD logs -f"
echo "   • Stack stoppen   → $COMPOSE_CMD down"
echo "   • Stack + Volumes → $COMPOSE_CMD down -v"
echo
if [[ "$ENV_CREATED" == true ]]; then
    info "Instanz-Anpassungen in docker-compose.override.yml pflegen:"
    echo "   cp docker-compose.override.yml.example docker-compose.override.yml"
    echo "   # z.B. eigene Ports, Volume-Pfade, zusätzliche ENV-Variablen"
    echo
fi
