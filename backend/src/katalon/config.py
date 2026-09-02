# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import json
from pathlib import Path
from typing import Annotated

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
    model_config = SettingsConfigDict(env_file=_resolve_env_files(), env_file_encoding="utf-8", extra="ignore")

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

    importer_max_upload_size_mb: int = 500
    importer_upload_ttl_seconds: int = 14400  # 4 hours

    portal_theme: str | None = None

    default_admin_email: str = "admin@katalon.dev"
    default_admin_password: str = "admin"
    katalon_base_url: str = ""
    first_run_credentials_path: str = "/var/lib/katalon/first-run-credentials.txt"

    oai_admin_email: str = "admin@katalon.dev"
    es_index_name: str = "katalon_records"

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

    @field_validator("cors_origins", mode="before")
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
    def _validate_smtp(self) -> "Settings":
        if not self.smtp_enabled:
            return self
        if not self.smtp_host or not self.smtp_from or not self.katalon_base_url:
            raise ValueError("SMTP_HOST, SMTP_FROM and KATALON_BASE_URL are required when SMTP_ENABLED=true")
        if bool(self.smtp_username) != bool(self.smtp_password):
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be set together")
        if self.smtp_starttls == self.smtp_ssl_tls:
            raise ValueError("Exactly one of SMTP_STARTTLS and SMTP_SSL_TLS must be true")
        return self



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
