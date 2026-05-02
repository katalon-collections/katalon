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

    cantaloupe_task_timeout: int = 120  # seconds to wait for Cantaloupe info.json

    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001", "http://localhost:4000", "http://localhost:4001"]


settings = Settings()
