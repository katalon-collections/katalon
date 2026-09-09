# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select

from katalon.api.v1 import (
    admin_config,
    ai,
    ark,
    audit,
    auth,
    authority,
    banners,
    batch,
    collections,
    crawlers,
    dnb_urn_mock,
    entities,
    export,
    export_mapping_sets,
    export_profiles,
    feedback,
    form_sections,
    form_variants,
    idno,
    importer,
    index_health,
    locks,
    media,
    metadata_mappings,
    oai,
    oai_sets,
    objects,
    occurrences,
    pages,
    pids,
    places,
    portal,
    portal_public,
    presence,
    procedures,
    record_subtypes,
    relations,
    schema_admin,
    search,
    sparql,
    storage_locations,
    theme,
    users,
    vocabularies,
    working_sets,
)
from katalon.api.v1.api_keys import router as api_keys_router
from katalon.api.v1.auth import hash_password
from katalon.config import settings
from katalon.core.dependencies import get_current_user
from katalon.core.limiter import limiter
from katalon.core.models import (
    AdminConfig,
    FieldDefinition,
    PortalConfig,
    User,
    Vocabulary,
    VocabularyTerm,
)
from katalon.core.models import (
    AuthoritySource as AuthoritySourceModel,
)
from katalon.database import AsyncSessionLocal
from katalon.services.relation_type_service import sync_relation_type_terms

OPENAPI_TAGS = [
    {"name": "system", "description": "Health-Check und Systemstatus."},
    {"name": "objects", "description": "Object records (Fotos, Dokumente, Gemälde)."},
    {"name": "entities", "description": "Entity records (Personen, Organisationen)."},
    {"name": "places", "description": "Place records (geografische Orte, PostGIS)."},
    {"name": "occurrences", "description": "Occurrence records (Werke, Ereignisse, Konzepte)."},
    {"name": "procedures", "description": "Vorgänge: Leihverkehr, Erwerbung, Restaurierung."},
    {"name": "relations", "description": "Generische Relationen zwischen den fünf Record-Typen."},
    {"name": "schema", "description": "field_definitions-Verwaltung (Schema-Engine)."},
    {"name": "record-subtypes", "description": "Konfigurierbare Subtypen je Record-Typ."},
    {"name": "form-variants", "description": "Konfigurierbare Formularvarianten je Record-Typ und Subtyp."},
    {"name": "vocabularies", "description": "Vokabulare und Terms."},
    {"name": "metadata-mappings", "description": "Mapping-Konfiguration für Importer/Export."},
    {"name": "media", "description": "Upload, IIIF-Tiles, Medien-Verknüpfung."},
    {"name": "search", "description": "Elasticsearch-Suche, Facetten, Reindex."},
    {"name": "importer", "description": "Excel/CSV/XML-Import, Dry Run, Batch."},
    {"name": "oai-pmh", "description": "OAI-PMH-Schnittstelle."},
    {"name": "auth", "description": "Login, Token, Passwort-Verwaltung."},
    {"name": "users", "description": "Nutzerverwaltung und Rollen."},
    {"name": "api-keys", "description": "API-Key-Verwaltung für Machine-to-Machine-Zugriff."},
    {"name": "authorities", "description": "Authority-Adapter (GND, Geonames) und Normdaten-Abgleich."},
    {"name": "audit", "description": "Audit-Log und Record-Snapshots (Versionierung)."},
    {"name": "admin", "description": "Admin-Konfiguration und Systemeinstellungen."},
    {"name": "banners", "description": "Portal-Hinweisbanner."},
    {"name": "theme", "description": "Portal-/Admin-Theming."},
    {"name": "pages", "description": "Statische Portal-Seiten."},
    {"name": "portal", "description": "Öffentliche Portal-Endpoints."},
    {"name": "pids", "description": "Persistent Identifiers."},
    {"name": "idno", "description": "Inventarnummern-Generierung."},
    {"name": "feedback", "description": "Nutzer-Feedback."},
    {"name": "ai", "description": "KI-gestützte Vorschläge (z. B. Auto-Mapping)."},
    {"name": "dnb-urn-mock", "description": "Test-Double für DNB-URN-Vergabe (nur Dev/Test)."},
    {"name": "working-sets", "description": "Arbeitslisten / Sets für Ad-hoc-Gruppierungen von Datensätzen."},
]

logger = logging.getLogger(__name__)
# 15 random bytes via token_urlsafe produce ~20 URL-safe chars (letters, digits, -,_).
FIRST_RUN_PASSWORD_TOKEN_BYTES = 15


def _derive_admin_email_from_base_url(base_url: str) -> str | None:
    parsed = urlparse(base_url)
    domain = parsed.hostname
    if not domain:
        return None
    return f"admin@{domain}"


def _write_first_run_credentials(email: str, password: str) -> None:
    credentials_path = Path(settings.first_run_credentials_path)
    credentials_path.parent.mkdir(parents=True, exist_ok=True)
    credentials_path.write_text(
        "\n".join(
            [
                "====== KATALON FIRST RUN ======",
                f"Base URL: {settings.katalon_base_url}",
                f"Email: {email}",
                f"Password: {password}",
                "Please change this password immediately after first login.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    credentials_path.chmod(0o600)


def _log_first_run_credentials(email: str, password: str) -> None:
    logger.warning("====== KATALON FIRST RUN ======")
    logger.warning("Base URL: %s", settings.katalon_base_url)
    logger.warning("Email: %s", email)
    logger.warning("Password: %s", password)
    logger.warning("Credentials file: %s", settings.first_run_credentials_path)
    logger.warning("Please change this password immediately after first login.")
    logger.warning("================================")


async def _ensure_admin() -> None:
    first_run_email: str | None = None
    first_run_password: str | None = None

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.role.in_(("admin", "superuser"))).limit(1)
        )
        if result.scalar_one_or_none() is None:
            base_url = settings.katalon_base_url.strip()
            if base_url:
                derived_admin_email = _derive_admin_email_from_base_url(base_url)
                if derived_admin_email is None:
                    logger.warning(
                        "Could not derive admin email from KATALON_BASE_URL '%s'; "
                        "falling back to DEFAULT_ADMIN_EMAIL.",
                        base_url,
                    )
                first_run_email = derived_admin_email or settings.default_admin_email
                first_run_password = secrets.token_urlsafe(FIRST_RUN_PASSWORD_TOKEN_BYTES)
                admin_email = first_run_email
                admin_password = first_run_password
                admin_role = "superuser"
            else:
                admin_email = settings.default_admin_email
                admin_password = settings.default_admin_password
                admin_role = "admin"
                logger.warning(
                    "KATALON_BASE_URL is empty; falling back to configured default admin credentials."
                )

            admin = User(
                email=admin_email,
                hashed_password=hash_password(admin_password),
                role=admin_role,
            )
            db.add(admin)
            await db.commit()

    if first_run_email and first_run_password:
        try:
            _write_first_run_credentials(first_run_email, first_run_password)
        except OSError:
            logger.exception(
                "Could not write first-run credentials file: %s. "
                "Retrieve credentials from the first-run log block.",
                settings.first_run_credentials_path,
            )
        _log_first_run_credentials(first_run_email, first_run_password)


_DEFAULT_MEDIA_TYPES = [
    ("vorderseite", {"de": "Vorderseite", "en": "Front"}),
    ("rueckseite",  {"de": "Rückseite",   "en": "Back"}),
    ("detail",      {"de": "Detail",      "en": "Detail"}),
    ("uebersicht",  {"de": "Übersicht",   "en": "Overview"}),
    ("innen",       {"de": "Innen",       "en": "Interior"}),
    ("signatur",    {"de": "Signatur",    "en": "Signature"}),
]


async def _ensure_media_types_vocab() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Vocabulary).where(Vocabulary.name == "media_types"))
        vocab = result.scalar_one_or_none()
        if vocab is None:
            vocab = Vocabulary(name="media_types", is_hierarchical=False)
            db.add(vocab)
            await db.flush()
            for term_key, label in _DEFAULT_MEDIA_TYPES:
                db.add(VocabularyTerm(vocabulary_id=vocab.id, term=term_key, label=label))
            await db.commit()


async def _ensure_relation_types_vocab() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Vocabulary).where(Vocabulary.name == "relation_types"))
        vocab = result.scalar_one_or_none()
        if vocab is None:
            vocab = Vocabulary(name="relation_types", is_hierarchical=False, kind="relation")
            db.add(vocab)
            await db.flush()
        elif vocab.kind != "relation":
            vocab.kind = "relation"
        has_terms = (
            await db.execute(select(VocabularyTerm.id).where(VocabularyTerm.vocabulary_id == vocab.id).limit(1))
        ).scalar_one_or_none()
        if has_terms is None:
            # Unrestricted system default so free relations always have a usable
            # type, even before an admin configures any relation vocabulary terms.
            db.add(
                VocabularyTerm(
                    vocabulary_id=vocab.id,
                    term="related_to",
                    label={"de": "ist verknüpft mit", "en": "is related to"},
                    inverse_label={"de": "ist verknüpft mit", "en": "is related to"},
                )
            )
        member_of_term = (
            await db.execute(
                select(VocabularyTerm.id).where(
                    VocabularyTerm.vocabulary_id == vocab.id,
                    VocabularyTerm.term == "member_of",
                )
            )
        ).scalar_one_or_none()
        if member_of_term is None:
            db.add(
                VocabularyTerm(
                    vocabulary_id=vocab.id,
                    term="member_of",
                    label={"de": "ist Teil von", "en": "is member of"},
                    inverse_label={"de": "enthält", "en": "contains"},
                    applies_from=["object"],
                    applies_to=["collection"],
                )
            )
        normal_location_term = (
            await db.execute(
                select(VocabularyTerm.id).where(
                    VocabularyTerm.vocabulary_id == vocab.id,
                    VocabularyTerm.term == "normal_location",
                )
            )
        ).scalar_one_or_none()
        if normal_location_term is None:
            db.add(
                VocabularyTerm(
                    vocabulary_id=vocab.id,
                    term="normal_location",
                    label={"de": "Standort ist", "en": "normal location is"},
                    inverse_label={"de": "ist Standort von", "en": "is normal location of"},
                    applies_from=["object"],
                    applies_to=["storage_location"],
                )
            )
        current_location_term = (
            await db.execute(
                select(VocabularyTerm.id).where(
                    VocabularyTerm.vocabulary_id == vocab.id,
                    VocabularyTerm.term == "current_location",
                )
            )
        ).scalar_one_or_none()
        if current_location_term is None:
            db.add(
                VocabularyTerm(
                    vocabulary_id=vocab.id,
                    term="current_location",
                    label={"de": "befindet sich aktuell in", "en": "current location is"},
                    inverse_label={"de": "ist aktueller Standort von", "en": "is current location of"},
                    applies_from=["object"],
                    applies_to=["storage_location"],
                )
            )
        await sync_relation_type_terms(db, vocab)
        await db.commit()


_DEFAULT_AUTHORITY_SOURCES = [
    ("gnd",       "Gemeinsame Normdatei (DNB)",        "katalon.integrations.gnd_adapter.GNDAdapter",         True),
    ("gnd-person",  "GND – Personennormdaten",         "katalon.integrations.gnd_adapter.GNDAdapter",         False),
    ("gnd-subject", "GND – Sachschlagwörter",          "katalon.integrations.gnd_adapter.GNDAdapter",         False),
    ("geonames",  "GeoNames",                          "katalon.integrations.geonames_adapter.GeonamesAdapter", False),
    ("viaf",      "VIAF (Virtual Int. Authority File)", "katalon.integrations.viaf_adapter.VIAFAdapter",        False),
    ("wikidata",  "Wikidata",                          "katalon.integrations.wikidata_adapter.WikidataAdapter", False),
    ("tgn",       "Getty Thesaurus of Geographic Names","katalon.integrations.tgn_adapter.TGNAdapter",          False),
    ("iconclass", "ICONCLASS",                         "katalon.integrations.iconclass_adapter.ICONCLASSAdapter", False),
    ("aat",       "Getty Art & Architecture Thesaurus", "katalon.integrations.aat_adapter.AATAdapter",          False),
]


async def _ensure_authority_sources() -> None:
    async with AsyncSessionLocal() as db:
        for src_id, label, adapter_class, is_enabled in _DEFAULT_AUTHORITY_SOURCES:
            result = await db.execute(
                select(AuthoritySourceModel).where(AuthoritySourceModel.id == src_id)
            )
            if result.scalar_one_or_none() is None:
                db.add(AuthoritySourceModel(
                    id=src_id,
                    label=label,
                    adapter_class=adapter_class,
                    config={},
                    is_enabled=is_enabled,
                ))
        await db.commit()


async def _ensure_portal_config() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PortalConfig).where(PortalConfig.key == "default"))
        if result.scalar_one_or_none() is None:
            db.add(PortalConfig(key="default"))
            await db.commit()


async def _ensure_admin_config() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AdminConfig).where(AdminConfig.key == "default"))
        if result.scalar_one_or_none() is None:
            db.add(AdminConfig(
                key="default",
                idno_schemas={},
                idno_patterns={},
                ai_base_url="https://api.openai.com/v1",
                ai_model="gpt-4.1-mini",
            ))
            await db.commit()


async def _ensure_label_fields() -> None:
    """Ensure every primary type has a generic 'label' field definition."""
    async with AsyncSessionLocal() as db:
        for target_type in (
            "object", "entity", "place", "occurrence", "procedure", "collection", "storage_location",
        ):
            result = await db.execute(
                select(FieldDefinition).where(
                    FieldDefinition.target_type == target_type,
                    FieldDefinition.target_subtype.is_(None),
                    FieldDefinition.name == "label",
                    FieldDefinition.is_deleted.is_(False),
                )
            )
            if result.scalar_one_or_none() is None:
                db.add(
                    FieldDefinition(
                        target_type=target_type,
                        target_subtype=None,
                        name="label",
                        label={"de": "Label", "en": "Label"},
                        field_type="text",
                        is_required=True,
                        is_repeatable=False,
                        is_searchable=True,
                        sort_order=0,
                        show_in_detail=True,
                        show_in_list=True,
                    )
                )
        await db.commit()


_DEFAULT_SECRETS = {
    "dev-secret-key-change-in-production",
    "change-me-in-production",
}

_DEFAULT_PASSWORDS = {"admin", "password", "katalon"}


def _check_production_secrets() -> None:
    if settings.debug:
        return
    errors = []
    if settings.secret_key in _DEFAULT_SECRETS or len(settings.secret_key) < 32:
        errors.append("SECRET_KEY is insecure — set a strong random value (>= 32 chars) via environment variable")
    if settings.default_admin_password in _DEFAULT_PASSWORDS:
        errors.append("DEFAULT_ADMIN_PASSWORD is set to a well-known default — change it before going live")
    if errors:
        raise RuntimeError("Refusing to start in production mode:\n" + "\n".join(f"  - {e}" for e in errors))


async def _check_cantaloupe_health() -> None:
    """Fail startup if Cantaloupe is unavailable; media uploads depend on it."""
    import httpx

    url = f"{settings.cantaloupe_url}/iiif/3"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Cantaloupe health check failed at {url} with HTTP {resp.status_code}. "
                    "Refusing to start without a working image server."
                )
            logger.info("Cantaloupe reachable at %s", settings.cantaloupe_url)
    except Exception as exc:
        raise RuntimeError(
            f"Cantaloupe unreachable at {url} ({exc}). "
            "Refusing to start without a working image server."
        ) from exc


def _check_media_root_writable() -> None:
    """Log a warning if MEDIA_ROOT isn't writable; uploads would otherwise fail silently per-request."""
    import os

    media_root = Path(settings.media_root)
    if not os.access(media_root, os.W_OK):
        logger.error(
            "MEDIA_ROOT %s is not writable by uid %d — uploads will fail with Permission denied. "
            "Fix ownership: chown %d:%d %s",
            media_root, os.getuid(), os.getuid(), os.getgid(), media_root,
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _check_production_secrets()
    _check_media_root_writable()
    await _ensure_admin()
    await _ensure_media_types_vocab()
    await _ensure_relation_types_vocab()
    await _ensure_portal_config()
    await _ensure_admin_config()
    await _ensure_authority_sources()
    await _ensure_label_fields()
    await _check_cantaloupe_health()
    try:
        from katalon.integrations.elasticsearch import ensure_index
        await ensure_index()
    except Exception:
        pass  # ES may not be available in all environments
    yield


try:
    _api_version = pkg_version("katalon")
except PackageNotFoundError:
    _api_version = "0.0.0-dev"

def _openapi_operation_id(route: APIRoute) -> str:
    """Return stable, unique, client-friendly operation IDs."""
    tag = route.tags[0] if route.tags else "default"
    method = min(route.methods).lower()
    path = route.path_format.strip("/").translate(str.maketrans("/{:-}", "_____"))
    return f"{tag}_{route.name}_{method}_{path}".replace("-", "_")


app = FastAPI(
    lifespan=lifespan,
    title="Katalon API",
    description="Metadata Management System for GLAM collections",
    version=_api_version,
    contact={"name": "Katalon Collections", "url": "https://github.com/katalon-collections/katalon"},
    license_info={"name": "AGPL-3.0-or-later", "identifier": "AGPL-3.0-or-later"},
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    openapi_tags=OPENAPI_TAGS,
    generate_unique_id_function=_openapi_operation_id,
)

def _rate_limit_handler(request: Request, exc: Exception) -> Response:
    """Adapt slowapi's handler (typed for RateLimitExceeded) to Starlette's Exception signature."""
    return _rate_limit_exceeded_handler(request, cast(RateLimitExceeded, exc))


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_authenticated = [Depends(get_current_user)]

app.include_router(admin_config.router, prefix="/v1", dependencies=_authenticated)
app.include_router(ai.router, prefix="/v1", dependencies=_authenticated)
app.include_router(index_health.router, prefix="/v1", dependencies=_authenticated)
app.include_router(idno.router, prefix="/v1", dependencies=_authenticated)
app.include_router(auth.router, prefix="/v1")
app.include_router(banners.router, prefix="/v1", dependencies=_authenticated)
app.include_router(users.router, prefix="/v1", dependencies=_authenticated)
app.include_router(objects.router, prefix="/v1", dependencies=_authenticated)
app.include_router(schema_admin.router, prefix="/v1", dependencies=_authenticated)
app.include_router(record_subtypes.router, prefix="/v1", dependencies=_authenticated)
app.include_router(form_variants.router, prefix="/v1", dependencies=_authenticated)
app.include_router(form_sections.router, prefix="/v1", dependencies=_authenticated)
app.include_router(vocabularies.router, prefix="/v1", dependencies=_authenticated)
app.include_router(audit.router, prefix="/v1", dependencies=_authenticated)
app.include_router(batch.router, prefix="/v1", dependencies=_authenticated)
app.include_router(entities.router, prefix="/v1", dependencies=_authenticated)
app.include_router(places.router, prefix="/v1", dependencies=_authenticated)
app.include_router(occurrences.router, prefix="/v1", dependencies=_authenticated)
app.include_router(procedures.router, prefix="/v1", dependencies=_authenticated)
app.include_router(collections.router, prefix="/v1", dependencies=_authenticated)
app.include_router(storage_locations.router, prefix="/v1", dependencies=_authenticated)
app.include_router(relations.router, prefix="/v1", dependencies=_authenticated)
app.include_router(presence.router, prefix="/v1", dependencies=_authenticated)
app.include_router(locks.router, prefix="/v1", dependencies=_authenticated)
app.include_router(media.router, prefix="/v1", dependencies=_authenticated)
app.include_router(media.batch_router, prefix="/v1", dependencies=_authenticated)
app.include_router(media.internal_router, prefix="/v1")
app.include_router(theme.router, prefix="/v1", dependencies=_authenticated)
app.include_router(portal.router, prefix="/v1", dependencies=_authenticated)
app.include_router(pages.router, prefix="/v1", dependencies=_authenticated)
app.include_router(search.router, prefix="/v1", dependencies=_authenticated)
app.include_router(authority.router, prefix="/v1", dependencies=_authenticated)
app.include_router(pids.router, prefix="/v1", dependencies=_authenticated)
app.include_router(importer.router, prefix="/v1", dependencies=_authenticated)
app.include_router(metadata_mappings.router, prefix="/v1", dependencies=_authenticated)
app.include_router(export.router, prefix="/v1", dependencies=_authenticated)
app.include_router(export_mapping_sets.router, prefix="/v1", dependencies=_authenticated)
app.include_router(export_profiles.router, prefix="/v1", dependencies=_authenticated)
app.include_router(oai.router, prefix="")
app.include_router(oai_sets.router, prefix="/v1", dependencies=_authenticated)
app.include_router(feedback.router, prefix="/v1", dependencies=_authenticated)
app.include_router(api_keys_router, prefix="/v1", dependencies=_authenticated)
app.include_router(working_sets.router, prefix="/v1", dependencies=_authenticated)
app.include_router(sparql.router, prefix="")
app.include_router(ark.router)
app.include_router(portal_public.router, prefix="/portal/v1")
app.include_router(crawlers.router, prefix="")

# Mock URN registrar is a test/dev fixture only — never expose its writable
# in-memory endpoints in production.
if settings.debug:
    app.include_router(dnb_urn_mock.router, prefix="/v1", dependencies=_authenticated)


@app.get("/health", tags=["system"])
async def health(response: Response) -> dict[str, object]:
    """Readiness check: verifies DB and Elasticsearch are reachable.

    Returns 503 if any dependency is down so load balancers can fail over.
    """
    from sqlalchemy import text

    from katalon.integrations.elasticsearch import get_es

    checks: dict[str, str] = {}

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        logger.warning("Health check: database unreachable", exc_info=True)
        checks["database"] = f"error: {exc.__class__.__name__}"

    es = get_es()
    try:
        if await es.ping():
            checks["elasticsearch"] = "ok"
        else:
            checks["elasticsearch"] = "error: ping failed"
    except Exception as exc:
        logger.warning("Health check: elasticsearch unreachable", exc_info=True)
        checks["elasticsearch"] = f"error: {exc.__class__.__name__}"
    finally:
        await es.close()

    healthy = all(v == "ok" for v in checks.values())
    if not healthy:
        response.status_code = 503
    return {"status": "ok" if healthy else "degraded", "checks": checks}
