"""Database reset helpers for the management CLI."""

from __future__ import annotations

import asyncio
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import click
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from katalon.core import models  # noqa: F401 - registers tables on Base.metadata
from katalon.database import Base

# Tables that are preserved by default because they contain configuration rather
# than collection data. alembic_version is always preserved.
_CONFIG_TABLES: set[str] = {
    "admin_config",
    "ai_usage_events",
    "api_keys",
    "app_secrets",
    "authority_sources",
    "banners",
    "field_definitions",
    "form_variant_role_defaults",
    "form_variants",
    "idno_counters",
    "import_mappings",
    "metadata_mappings",
    "oai_sets",
    "portal_config",
    "record_subtypes",
    "role_permissions",
    "static_pages",
    "users",
    "vocabularies",
    "vocabulary_terms",
}

_ALWAYS_EXCLUDED = {"alembic_version"}


def _to_pg_url(asyncpg_url: str) -> str:
    """Strip the +asyncpg driver prefix for libpq-based tools."""
    return asyncpg_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def _pg_env(asyncpg_url: str) -> dict[str, str]:
    """Return environment for pg_dump with libpq-compatible URL."""
    url = _to_pg_url(asyncpg_url)
    env = os.environ.copy()
    env["PGDATABASE"] = url.rsplit("/", 1)[-1]
    return env


def _pg_conn_args(asyncpg_url: str) -> list[str]:
    """Build host/port/user arguments for pg_dump from an asyncpg URL."""
    url = _to_pg_url(asyncpg_url)
    # Very small parser: postgresql://user:pass@host:port/dbname
    rest = url.split("://", 1)[1]
    auth_host, dbname = rest.rsplit("/", 1)
    if "@" in auth_host:
        auth, host_port = auth_host.split("@", 1)
    else:
        auth, host_port = "", auth_host
    parts = host_port.split(":")
    host = parts[0]
    port = parts[1] if len(parts) > 1 else "5432"

    args = ["--host", host, "--port", port, "--dbname", dbname]
    if auth:
        user = auth.split(":", 1)[0]
        args.extend(["--username", user])
    return args


def _backup_path(backup_dir: str | None) -> Path:
    directory = Path(backup_dir) if backup_dir else Path.cwd()
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return directory / f"katalon_backup_{timestamp}.sql"


async def _dump_database(backup_file: Path) -> None:
    """Run pg_dump for the configured database."""
    from katalon.config import settings

    cmd = [
        "pg_dump",
        *_pg_conn_args(settings.database_url),
        "--clean",
        "--if-exists",
        "--file",
        str(backup_file),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        env=_pg_env(settings.database_url),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"pg_dump failed (exit {proc.returncode}): {stderr.decode(errors='replace')[:500]}"
        )


async def _do_reset(engine: AsyncEngine, wipe_all: bool) -> list[str]:
    """Compute and truncate the target tables.

    Returns the list of truncated table names.
    """
    excluded = set(_ALWAYS_EXCLUDED)
    if not wipe_all:
        excluded.update(_CONFIG_TABLES)

    # sorted_tables is create-order (parents first); truncate children first.
    target_tables = [
        t.name for t in reversed(Base.metadata.sorted_tables) if t.name not in excluded
    ]
    if not target_tables:
        return []

    async with engine.begin() as conn:
        for table_name in target_tables:
            await conn.execute(
                text(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE')
            )
    return target_tables


def db_reset(wipe_all: bool, backup_dir: str | None, no_backup: bool, confirm: bool) -> None:
    """Reset Katalon data tables.

    Args:
        wipe_all: Also truncate configuration tables.
        backup_dir: Directory for the pg_dump backup.
        no_backup: Skip the backup step.
        confirm: If True, ask for interactive confirmation.
    """
    from katalon.config import settings
    from katalon.database import engine

    backup_file: Path | None = None
    if not no_backup:
        backup_file = _backup_path(backup_dir)

    scope = "ALL tables" if wipe_all else "DATA tables (config preserved)"
    click.echo(f"Database: {settings.database_url.replace('://', '://***@')}")
    click.echo(f"Scope:    {scope}")
    if backup_file:
        click.echo(f"Backup:   {backup_file}")
    else:
        click.echo("Backup:   skipped")

    if confirm:
        prompt = "Type 'reset' to continue"
        if wipe_all:
            prompt += " (including config)"
        response = click.prompt(prompt)
        if response.strip().lower() != "reset":
            click.echo("Aborted.")
            raise click.Abort()

    async def _run() -> None:
        if backup_file:
            click.echo("Running pg_dump ...")
            await _dump_database(backup_file)
            click.echo(f"Backup written to {backup_file}")

        click.echo("Truncating tables ...")
        truncated = await _do_reset(engine, wipe_all)
        click.echo(f"Truncated {len(truncated)} tables: {', '.join(truncated)}")

    asyncio.run(_run())
