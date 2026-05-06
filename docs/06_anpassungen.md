# Katalon – Anleitung für tiefgreifende Anpassungen

Dieses Dokument beschreibt, wo und wie man an zentralen Erweiterungspunkten ansetzt, ohne die gesamte Codebasis verstehen zu müssen.

---

## 1. Neuen Normdaten-Adapter implementieren

Normdaten-Adapter (GND, Geonames, Wikidata etc.) folgen einem einheitlichen Plugin-Muster. Einen neuen hinzufügen geht ohne Änderung am restlichen Code.

### Wo der Code liegt

```
backend/src/katalon/integrations/
├── authority.py          ← Abstrakte Basisklasse + AuthorityHit-Dataclass
├── gnd_adapter.py        ← Referenz-Implementierung (lobid.org)
├── geonames_adapter.py
└── ...
backend/src/katalon/services/
└── authority_service.py  ← Registry: _BUILTIN-Dict, Adapter-Loader
```

### Schritt-für-Schritt

**Schritt 1 — Adapter-Datei anlegen**

```python
# backend/src/katalon/integrations/mein_adapter.py
import httpx
from .authority import AuthorityHit, AuthoritySource

class MeinAdapter(AuthoritySource):
    source_id = "mein-system"          # eindeutiger Bezeichner

    async def search(self, query: str, limit: int = 10) -> list[AuthorityHit]:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("https://api.beispiel.de/search",
                                 params={"q": query, "rows": limit})
            r.raise_for_status()
        hits = []
        for item in r.json().get("results", []):
            hits.append(AuthorityHit(
                source=self.source_id,
                external_id=item["id"],
                label=item["name"],
                description=item.get("note", ""),
                extra=item,             # alles weitere landet hier
            ))
        return hits

    async def fetch(self, external_id: str) -> AuthorityHit | None:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://api.beispiel.de/record/{external_id}")
            if r.status_code == 404:
                return None
            r.raise_for_status()
        item = r.json()
        return AuthorityHit(
            source=self.source_id,
            external_id=external_id,
            label=item["name"],
            description=item.get("note", ""),
            extra=item,
        )
```

**Schritt 2 — In der Registry registrieren**

```python
# backend/src/katalon/services/authority_service.py
from katalon.integrations.mein_adapter import MeinAdapter

_BUILTIN: dict[str, AuthoritySource] = {
    "gnd":        GNDAdapter(),
    "geonames":   GeonamesAdapter(),
    "mein-system": MeinAdapter(),      # ← neu
    # ...
}
```

Das war's. Der Adapter ist sofort unter `GET /v1/authorities/search?source=mein-system&q=...` erreichbar.

### Adapter ohne Code-Änderung (DB-Weg)

Für externe oder institutionelle Adapter, die nicht in den Core gehören, kann man den Adapter auch über die Datenbank registrieren:

```sql
INSERT INTO authority_sources (id, label, adapter_class, config, is_enabled)
VALUES (
  'mein-system',
  'Mein System',
  'katalon.integrations.mein_adapter.MeinAdapter',  -- vollständiger Python-Pfad
  '{}',
  true
);
```

`authority_service._load_registry()` lädt dann den Adapter per `importlib.import_module`. Das Modul muss im Python-Path sein (also z.B. als installiertes Package oder in `PYTHONPATH`).

### Adapter mit Konfiguration (API-Keys)

Wenn der Adapter Credentials braucht:

```python
class MeinAdapter(AuthoritySource):
    source_id = "mein-system"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    async def search(self, query, limit=10):
        headers = {"Authorization": f"Bearer {self.api_key}"}
        ...
```

Config in der DB:
```json
{ "api_key": "mein-geheimer-schluessel" }
```

Der `_load_registry()` übergibt `config` als `kwargs` an den Konstruktor.

---

## 2. Portal-UI grundlegend umgestalten

Das Portal (`frontend/portal/`) ist eine Standard-React-App mit React Router v6. Es gibt keine Component-Library, nur eigene CSS Custom Properties — das macht Umstrukturierungen einfach.

### Einstiegspunkte

```
frontend/portal/src/
├── App.tsx       ← Layout-Wrapper: Header, Footer, Routes
├── styles.css    ← Alle Styles (Custom Properties: --fg, --bg, --accent, ...)
└── pages/        ← Eine Datei pro Route
```

### Beispiel: Linke Sidebar statt Top-Navigation

**1. Layout in `App.tsx` ändern**

Statt `<Header>` oben eine `<Sidebar>` links einbauen:

```tsx
// App.tsx — vorher:
<>
  <Header />
  <Routes>...</Routes>
  <Footer />
</>

// App.tsx — nachher:
<div className="app-shell">
  <Sidebar />
  <main className="content">
    <Routes>...</Routes>
  </main>
</div>
```

**2. CSS anpassen (`styles.css`)**

```css
.app-shell {
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: 100vh;
}

.content {
  overflow-y: auto;
}
```

**3. Neue `Sidebar.tsx`-Komponente**

```tsx
// src/components/Sidebar.tsx
import { Link, useLocation } from 'react-router-dom'

export function Sidebar() {
  const { pathname } = useLocation()
  return (
    <nav className="sidebar">
      <div className="logo">Katalon</div>
      <Link to="/search?type=object" className={pathname.startsWith('/objects') ? 'active' : ''}>
        Objekte
      </Link>
      ...
    </nav>
  )
}
```

**Wonach noch suchen:** `Header` und `Footer` in `App.tsx` — beide sind kleine Komponenten in derselben Datei und können direkt durch Sidebar-Logik ersetzt werden.

### Neues Theme

Alle Farben sind CSS Custom Properties auf `:root` — kein Sass, kein Theme-File. Überschreiben über:
1. `styles.css` direkt bearbeiten (persistiert im Code)
2. Admin-Einstellungen → Farben (persistiert in `portal_config`, wird bei jedem App-Start angewendet)
3. Eigene CSS-Datei nach `styles.css` importieren (in `main.tsx`)

### Neue Seiten / Routen

In `App.tsx`:
```tsx
<Route path="/meine-seite" element={<MeineSeitePage />} />
```

Dann `src/pages/MeineSeitePage.tsx` anlegen.

---

## 3. Identity Management / SSO anbinden

Katalon verwendet selbst gebautes JWT-Auth (kein externer Provider). Das ist der Einstiegspunkt für eine SSO-Integration.

### Wie Auth aktuell funktioniert

```
POST /v1/auth/token
  ├── bcrypt.verify(password, hashed_password)
  ├── jose.jwt.encode({sub: user_id, role, exp})
  └── → {access_token}

Folgeaufrufe:
  Authorization: Bearer <token>
  └── get_current_user() in dependencies.py
      ├── jwt.decode(token, SECRET_KEY)
      └── DB lookup: users-Tabelle
```

**Relevante Dateien:**
- `backend/src/katalon/api/v1/auth.py` — Login-Endpoint (`POST /token`), Token-Generierung
- `backend/src/katalon/core/dependencies.py` — `get_current_user()`, `require_role()`
- `backend/src/katalon/core/models.py` — `User`-Tabelle
- `frontend/admin/src/api/client.ts` — Token-Storage, `onUnauthorized`-Callback

### Option A: SAML/OIDC (Shibboleth, Keycloak, Azure AD)

Der sauberste Weg: ein externer Provider stellt das JWT aus, Katalon validiert es nur noch.

**Backend — `dependencies.py` anpassen:**

```python
# Statt lokalem SECRET_KEY: JWKS-Endpoint des Providers verwenden
from jose import jwt
from jose.backends import RSAKey
import httpx

async def get_current_user(token: str = Depends(oauth2_scheme), db: DBDep = None):
    # JWKS vom IdP laden (gecacht)
    jwks = await _load_jwks("https://idp.institution.de/.well-known/jwks.json")
    payload = jwt.decode(token, jwks, algorithms=["RS256"],
                         audience="katalon")
    # Payload-Claims auf Katalon-Rollen mappen:
    email = payload.get("email") or payload.get("upn")
    role = _map_groups_to_role(payload.get("groups", []))
    # User in DB anlegen/aktualisieren (JIT-Provisioning):
    user = await _upsert_user(db, email, role)
    return user
```

**Backend — Login-Redirect:**

Der `/v1/auth/token`-Endpoint kann alternativ auf den IdP-SSO-URL redirecten (OIDC Authorization Code Flow). Dafür eignet sich `authlib` (Python-Bibliothek für OIDC/OAuth2).

**Frontend — Admin-UI:**

In `ScreenLogin.tsx` den Login-Button durch einen Redirect auf den IdP ersetzen:
```tsx
<button onClick={() => window.location.href = "/v1/auth/sso/redirect"}>
  Mit Institutions-Account anmelden
</button>
```

Das Backend-Endpoint `/v1/auth/sso/redirect` leitet zum IdP weiter, der Callback `/v1/auth/sso/callback` tauscht den Code gegen ein Token und setzt ein Katalon-JWT.

**Empfohlene Library:** `authlib` — unterstützt OIDC, SAML, OAuth2 und lässt sich sauber in FastAPI integrieren.

### Option B: LDAP (Active Directory, OpenLDAP)

Einfacher einzubauen: nur der Login-Schritt ändert sich.

**`auth.py` — `verify_password` ersetzen:**

```python
import ldap3

def verify_ldap(username: str, password: str) -> bool:
    server = ldap3.Server("ldaps://ldap.institution.de")
    conn = ldap3.Connection(server,
                            user=f"uid={username},ou=users,dc=institution,dc=de",
                            password=password,
                            auto_bind=True)
    return conn.bound
```

Der Rest (JWT-Ausstellung, `get_current_user`) bleibt unverändert. Katalon bleibt der Token-Aussteller, LDAP übernimmt nur die Credential-Prüfung.

**Rollen:** LDAP-Gruppen auf Katalon-Rollen mappen:
```python
groups = _get_ldap_groups(username)
role = "admin" if "katalon-admins" in groups else "editor"
```

### Option C: Reverse Proxy Auth (Shibboleth SP, mod_auth_mellon)

Wenn der Webserver bereits Auth übernimmt (häufig in Hochschulumgebungen):

```nginx
# nginx: Shibboleth-Header weiterleiten
location /v1/ {
    auth_request /shibboleth-check;
    proxy_set_header X-Remote-User $http_remote_user;
    proxy_set_header X-Remote-Groups $http_remote_groups;
    proxy_pass http://api/v1/;
}
```

FastAPI liest dann den Header:

```python
# dependencies.py
from fastapi import Header

async def get_current_user(
    x_remote_user: str | None = Header(default=None),
    db: DBDep = None,
):
    if not x_remote_user:
        raise HTTPException(401)
    role = _map_groups(x_remote_user)
    user = await _upsert_user(db, x_remote_user, role)
    return user
```

**Wichtig:** Diese Option setzt voraus, dass nur der Reverse Proxy auf Port 8000 zugreifen kann (Firewall, Docker-Network). Direkte API-Aufrufe ohne den Proxy umgehen sonst die Auth.

### Was in jedem Fall gleich bleibt

- Die `users`-Tabelle kann für JIT-Provisioning weiterverwendet werden (User wird beim ersten SSO-Login angelegt).
- `require_role()` in `dependencies.py` muss nicht geändert werden, solange `current_user.role` korrekt befüllt ist.
- Das Admin-Frontend speichert weiterhin ein Bearer-Token in `localStorage` — das kann ein selbst ausgestelltes Katalon-JWT sein, auch wenn die Credential-Prüfung extern passiert.

---

## 4. Neues OAI-PMH-Metadatenformat hinzufügen

→ Vollständige Anleitung in [05_oai_serialisierungen.md](./05_oai_serialisierungen.md)

---

## Schnellreferenz: Wo fange ich an?

| Vorhaben | Dateien |
|---|---|
| Neuer Normdaten-Adapter | `integrations/<name>_adapter.py` + `services/authority_service.py` |
| Portal-Layout umbauen | `frontend/portal/src/App.tsx` + `styles.css` |
| Portal-Farben anpassen | Admin-UI → Einstellungen, oder `styles.css` direkt |
| Neue Portal-Route | `App.tsx` (Route) + `pages/<Name>Page.tsx` |
| SSO (OIDC/SAML) | `api/v1/auth.py` + `core/dependencies.py` |
| SSO via LDAP | `api/v1/auth.py` (nur Login-Schritt) |
| SSO via Reverse Proxy | nginx-Config + `core/dependencies.py` |
| Neues OAI-Format | `services/oaipmh_service.py` + `api/v1/oai.py` |
| Neues Feld für alle Records | `migrations/` (Alembic) + `core/models.py` + `core/schemas.py` |
| Neue Admin-Seite | `components/screens/Screen<Name>.tsx` + `layout/AppShell.tsx` + `layout/Sidebar.tsx` |
