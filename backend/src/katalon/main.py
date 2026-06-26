import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select

from katalon.api.v1 import (
    admin_config,
    audit,
    auth,
    authority,
    banners,
    dnb_urn_mock,
    entities,
    feedback,
    idno,
    importer,
    index_health,
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
    procedures,
    record_subtypes,
    relations,
    schema_admin,
    search,
    theme,
    users,
    vocabularies,
)
from katalon.api.v1.api_keys import router as api_keys_router
from katalon.api.v1.auth import hash_password
from katalon.config import settings
from katalon.core.limiter import limiter
from katalon.core.models import (
    AdminConfig,
    FieldDefinition,
    PortalConfig,
    RecordSubtype,
    User,
    Vocabulary,
    VocabularyTerm,
)
from katalon.core.models import (
    AuthoritySource as AuthoritySourceModel,
)
from katalon.database import AsyncSessionLocal

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


_DEFAULT_AUTHORITY_SOURCES = [
    ("gnd",       "Gemeinsame Normdatei (DNB)",        "katalon.integrations.gnd_adapter.GNDAdapter",         True),
    ("geonames",  "GeoNames",                          "katalon.integrations.geonames_adapter.GeonamesAdapter", False),
    ("viaf",      "VIAF (Virtual Int. Authority File)", "katalon.integrations.viaf_adapter.VIAFAdapter",        False),
    ("wikidata",  "Wikidata",                          "katalon.integrations.wikidata_adapter.WikidataAdapter", False),
    ("tgn",       "Getty Thesaurus of Geographic Names","katalon.integrations.tgn_adapter.TGNAdapter",          False),
    ("iconclass", "ICONCLASS",                         "katalon.integrations.iconclass_adapter.ICONCLASSAdapter", False),
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
            db.add(AdminConfig(key="default", idno_schemas={}, idno_patterns={}))
            await db.commit()


async def _ensure_label_fields() -> None:
    """Ensure every primary type has a generic 'label' field definition."""
    async with AsyncSessionLocal() as db:
        for target_type in ("object", "entity", "place", "occurrence", "procedure"):
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
                    )
                )
        await db.commit()


_DEFAULT_RECORD_SUBTYPES = [
    # (primary_type, name, label_de, label_en)
    ("object",     "objekt",       "Objekt",       "Object"),
    ("entity",     "person",       "Person",       "Person"),
    ("place",      "geographikum", "Geographikum", "Geographic"),
    ("occurrence", "werk",         "Werk",         "Work"),
]


async def _ensure_record_subtypes() -> None:
    """Ensure every primary type has at least one default subtype."""
    async with AsyncSessionLocal() as db:
        for primary_type, name, label_de, label_en in _DEFAULT_RECORD_SUBTYPES:
            result = await db.execute(
                select(RecordSubtype).where(
                    RecordSubtype.primary_type == primary_type,
                    RecordSubtype.name == name,
                )
            )
            if result.scalar_one_or_none() is None:
                db.add(
                    RecordSubtype(
                        primary_type=primary_type,
                        name=name,
                        label={"de": label_de, "en": label_en},
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
    """Ping Cantaloupe at startup so misconfiguration surfaces in logs, not on first upload."""
    import httpx

    url = f"{settings.cantaloupe_url}/iiif/3"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                logger.warning(
                    "Cantaloupe health check at %s returned HTTP %d — "
                    "IIIF tile generation will fail",
                    url,
                    resp.status_code,
                )
            else:
                logger.info("Cantaloupe reachable at %s", settings.cantaloupe_url)
    except Exception as exc:
        logger.warning(
            "Cantaloupe unreachable at %s (%s) — "
            "IIIF tile generation will fail until this is fixed",
            url,
            exc,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_production_secrets()
    await _ensure_admin()
    await _ensure_media_types_vocab()
    await _ensure_record_subtypes()
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


app = FastAPI(
    lifespan=lifespan,
    title="Katalon API",
    description="Metadata Management System for GLAM collections",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_config.router, prefix="/v1")
app.include_router(index_health.router, prefix="/v1")
app.include_router(idno.router, prefix="/v1")
app.include_router(auth.router, prefix="/v1")
app.include_router(banners.router, prefix="/v1")
app.include_router(users.router, prefix="/v1")
app.include_router(objects.router, prefix="/v1")
app.include_router(schema_admin.router, prefix="/v1")
app.include_router(record_subtypes.router, prefix="/v1")
app.include_router(vocabularies.router, prefix="/v1")
app.include_router(audit.router, prefix="/v1")
app.include_router(entities.router, prefix="/v1")
app.include_router(places.router, prefix="/v1")
app.include_router(occurrences.router, prefix="/v1")
app.include_router(procedures.router, prefix="/v1")
app.include_router(relations.router, prefix="/v1")
app.include_router(media.router, prefix="/v1")
app.include_router(media.batch_router, prefix="/v1")
app.include_router(theme.router, prefix="/v1")
app.include_router(portal.router, prefix="/v1")
app.include_router(pages.router, prefix="/v1")
app.include_router(search.router, prefix="/v1")
app.include_router(authority.router, prefix="/v1")
app.include_router(pids.router, prefix="/v1")
app.include_router(importer.router, prefix="/v1")
app.include_router(metadata_mappings.router, prefix="/v1")
app.include_router(oai.router, prefix="/v1")
app.include_router(oai_sets.router, prefix="/v1")
app.include_router(feedback.router, prefix="/v1")
app.include_router(api_keys_router, prefix="/v1")

# Mock URN registrar is a test/dev fixture only — never expose its writable
# in-memory endpoints in production.
if settings.debug:
    app.include_router(dnb_urn_mock.router, prefix="/v1")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
