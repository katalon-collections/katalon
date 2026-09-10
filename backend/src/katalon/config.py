# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from katalon.errors import KatalonSecretsKeyError


def _resolve_env_files() -> tuple[str, ...]:
    """Resolve .env files independent of the current working directory.

    Ordered by precedence (later files win). The repo root .env is the
    canonical source, so it is listed last and overrides backend/.env.
    """
    backend_dir = Path(__file__).resolve().parents[2]
    env_files = [backend_dir / ".env"]
    if backend_dir.name == "backend":
        env_files.append(backend_dir.parent / ".env")
    return tuple(map(str, env_files))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_resolve_env_files(), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+asyncpg://katalon:katalon@localhost:5432/katalon"
    redis_url: str = "redis://localhost:6379/0"
    elasticsearch_url: str = "http://localhost:9200"
    cantaloupe_url: str = "http://localhost:8182"
    cantaloupe_public_url: str = ""  # if set, used in IIIF manifests instead of cantaloupe_url

    secret_key: str = "dev-secret-key-change-in-production"
    katalon_secrets_key: str = Field(min_length=32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8
    refresh_token_expire_days: int = 30

    media_root: str = "/var/lib/katalon/media"
    max_upload_size_mb: int = 100
    purge_after_days: int = 30

    # Medien-Speicherbackend (strikt opt-in; Default local = unverändertes Verhalten).
    # S3Storage zielt auf alle S3-kompatiblen Implementierungen (Ceph RADOSGW,
    # MinIO, Hetzner, Garage, AWS) — siehe media_storage.S3Storage.
    storage_backend: Literal["local", "s3"] = "local"
    s3_endpoint_url: str = ""  # leer = AWS-Default
    s3_bucket: str = ""
    s3_region: str = "us-east-1"  # RADOSGW/MinIO ignorieren die Region, SigV4 braucht aber einen Wert
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_force_path_style: bool = True  # funktioniert überall ohne DNS-Wildcard-Setup
    s3_verify_tls: bool = True  # False nur für Dev/Test
    s3_ca_bundle: str = ""  # optional: Pfad zu interner/self-signed CA (On-Prem-Ceph)

    importer_max_upload_size_mb: int = 500
    importer_upload_ttl_seconds: int = 14400  # 4 hours

    portal_theme: str | None = None

    default_admin_email: str = "admin@katalon.dev"
    default_admin_password: str = "admin"
    katalon_base_url: str = ""
    first_run_credentials_path: str = "/var/lib/katalon/first-run-credentials.txt"

    oai_admin_email: str = "admin@katalon.dev"
    es_index_name: str = "katalon_records"
    es_reindex_batch_size: int = 500

    geonames_username: str = "demo"
    wikidata_user_agent: str = ""

    dnb_urn_enabled: bool = False
    dnb_urn_api_url: str = "https://api.nbn-resolving.org/v2/"
    dnb_urn_namespace: str = ""
    dnb_urn_username: str = ""
    dnb_urn_password: str = ""
    dnb_urn_resolver_url: str = "https://nbn-resolving.org/"

    # ARK: lokal geprägt. Erst nach Vergabe eines produktiven NAAN aktivieren.
    ark_enabled: bool = False
    ark_naan: str = ""
    ark_resolver_url: str = "https://n2t.net/"
    ark_suffix_length: int = 10

    # Triple Store (Oxigraph) & RDF-Projektion
    oxigraph_enabled: bool = False
    oxigraph_url: str = "http://localhost:7878"
    sparql_endpoint_enabled: bool = True
    sparql_require_auth: bool = True
    sparql_query_timeout: float = Field(default=30.0, gt=0)
    sparql_max_query_length: int = Field(default=65536, gt=0)  # 64 KB
    cantaloupe_task_timeout: int = 120  # seconds to wait for Cantaloupe info.json

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    ai_request_timeout_seconds: int = 60

    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    smtp_ssl_tls: bool = False
    smtp_timeout_seconds: int = Field(default=10, gt=0)

    debug: bool = False
    # NoDecode: docker-compose/dotenv strippen Quotes in Umgebungswerten, wodurch
    # das Default-JSON-Parsing von pydantic-settings scheitert. Stattdessen hier
    # tolerant parsen: JSON-Array, gemangelte Variante ohne Quotes, oder
    # kommagetrennte Liste.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    cors_origin_regex: str | None = None

    # --- Rate Limiting (öffentliche/anonyme Endpunkte) ---
    # slowapi-Syntax "N/unit" (z. B. "30/minute", "500/hour"). Login/Password-Reset
    # bleiben bewusst hartkodiert (Brute-Force-Schutz, kein Crawler-Thema).
    rate_limit_default: str = "200/minute"
    rate_limit_public_export: str = "30/minute"
    rate_limit_public_search: str = "100/minute"
    rate_limit_oai: str = "100/minute"
    rate_limit_authority_proxy: str = "60/minute"
    rate_limit_sparql: str = "60/minute"
    # Zählerspeicher für slowapi. Leer = In-Process-Speicher, korrekt nur bei
    # genau einem API-Worker/-Container. Produktiv auf die Redis-URL setzen,
    # sonst hat jeder Worker seinen eigenen Zähler und das effektive Limit ist
    # ein Vielfaches des konfigurierten Werts.
    rate_limit_storage_uri: str = ""

    # --- Crawler-Steuerung ---
    robots_disallow_paths: Annotated[list[str], NoDecode] = ["/v1/"]
    llms_txt_enabled: bool = True
    llms_txt_extra_notes: str = ""

    @field_validator("cors_origin_regex", mode="before")
    @classmethod
    def _parse_cors_origin_regex(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    @field_validator("cors_origins", "robots_disallow_paths", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        raw = v.strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(o).strip() for o in parsed if str(o).strip()]
        return [o.strip().strip("[]") for o in raw.split(",") if o.strip().strip("[]")]

    @model_validator(mode="after")
    def _validate_storage_backend(self) -> "Settings":
        if self.storage_backend == "s3":
            missing = [
                name
                for name, value in (
                    ("S3_BUCKET", self.s3_bucket),
                    ("S3_ACCESS_KEY", self.s3_access_key),
                    ("S3_SECRET_KEY", self.s3_secret_key),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    f"{', '.join(missing)} required when STORAGE_BACKEND=s3 "
                    "(S3Storage braucht Bucket und Credentials)"
                )
        return self

    @model_validator(mode="after")
    def _validate_smtp(self) -> "Settings":
        if not self.smtp_enabled:
            return self
        if not self.smtp_host or not self.smtp_from or not self.katalon_base_url:
            raise ValueError(
                "SMTP_HOST, SMTP_FROM and KATALON_BASE_URL are required when SMTP_ENABLED=true"
            )
        if bool(self.smtp_username) != bool(self.smtp_password):
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be set together")
        if self.smtp_starttls == self.smtp_ssl_tls:
            raise ValueError("Exactly one of SMTP_STARTTLS and SMTP_SSL_TLS must be true")
        return self

    @property
    def oai_repository_domain(self) -> str:
        """Domain segment for OAI-PMH identifiers (``oai:<domain>:<type>:<id>``).

        OAI-PMH 2.4 / RFC 4151 require the identifier to embed a domain the
        repository controls, so identifiers stay globally unique across
        independent Katalon installations. Falls back to a placeholder when
        no base URL is configured (e.g. local dev without KATALON_BASE_URL).
        """
        from urllib.parse import urlparse

        host = urlparse(self.katalon_base_url).hostname if self.katalon_base_url else None
        return host or "katalon.example"


def _build_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        fields = {str(e.get("loc", ())[0]) for e in exc.errors()}
        if "katalon_secrets_key" in fields:
            raise KatalonSecretsKeyError(
                "KATALON_SECRETS_KEY muss gesetzt und mindestens 32 Zeichen lang sein. "
                "Setze die Umgebungsvariable (z. B. export KATALON_SECRETS_KEY=..."
                ") oder trage sie in .env ein (Vorlage: .env.example)."
            ) from exc
        raise


settings = _build_settings()
