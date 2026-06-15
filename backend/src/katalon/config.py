from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://katalon:katalon@localhost:5432/katalon"
    redis_url: str = "redis://localhost:6379/0"
    elasticsearch_url: str = "http://localhost:9200"
    cantaloupe_url: str = "http://localhost:8182"
    cantaloupe_public_url: str = ""  # if set, used in IIIF manifests instead of cantaloupe_url

    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    media_root: str = "/var/lib/katalon/media"
    max_upload_size_mb: int = 100

    portal_theme: str | None = None

    default_admin_email: str = "admin@katalon.dev"
    default_admin_password: str = "admin"
    katalon_base_url: str = ""
    first_run_credentials_path: str = "/var/lib/katalon/first-run-credentials.txt"

    oai_admin_email: str = "admin@katalon.dev"
    geonames_username: str = "demo"

    dnb_urn_enabled: bool = False
    dnb_urn_api_url: str = "https://api.nbn-resolving.org/v2/"
    dnb_urn_namespace: str = ""
    dnb_urn_username: str = ""
    dnb_urn_password: str = ""
    dnb_urn_resolver_url: str = "https://nbn-resolving.org/"

    cantaloupe_task_timeout: int = 120  # seconds to wait for Cantaloupe info.json

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    debug: bool = False
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:4000",
        "http://localhost:4001",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


settings = Settings()
