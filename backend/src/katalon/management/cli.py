# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Management CLI for Katalon development and operations.

Commands:
    katalon-manage db-reset
    katalon-manage import-csv
    katalon-manage import-xml
    katalon-manage reset-admin
"""

from __future__ import annotations

from importlib.metadata import version as get_version

import click

from katalon.management.db_reset import db_reset as db_reset_impl
from katalon.management.import_cmd import import_csv as import_csv_impl
from katalon.management.import_cmd import import_xml as import_xml_impl
from katalon.management.reset_admin import reset_admin as reset_admin_impl


@click.group()
@click.version_option(version=get_version("katalon"), prog_name="katalon-manage")
def cli() -> None:
    """Katalon management CLI."""


@cli.command(name="db-reset")
@click.option(
    "--all",
    "wipe_all",
    is_flag=True,
    help="Also truncate configuration tables (users, vocabularies, field definitions, ...).",
)
@click.option(
    "--backup-dir",
    type=click.Path(file_okay=False, dir_okay=True, writable=True, path_type=str),
    help="Directory for a pg_dump backup before truncation. Defaults to current directory.",
)
@click.option(
    "--no-backup",
    is_flag=True,
    help="Skip the pg_dump backup before truncation.",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip interactive confirmation.",
)
def db_reset(wipe_all: bool, backup_dir: str | None, no_backup: bool, yes: bool) -> None:
    """Reset Katalon data tables.

    By default configuration tables (users, field definitions, vocabularies, ...)
    are preserved. Use --all to truncate everything except alembic_version.
    """
    db_reset_impl(wipe_all=wipe_all, backup_dir=backup_dir, no_backup=no_backup, confirm=not yes)


@cli.command(name="import-csv")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=str))
@click.option("--type", "record_type", required=True, type=str, help="Record type: object, entity, place or occurrence.")
@click.option("--mapping", required=True, type=click.Path(exists=True, dir_okay=False, path_type=str), help="JSON mapping file.")
@click.option("--subtype", type=str, help="Record subtype.")
@click.option("--idno-strategy", default="auto", type=click.Choice(["auto", "column", "skip"]), help="ID number strategy.")
@click.option("--upsert-strategy", default="skip", type=click.Choice(["skip", "merge", "replace"]), help="Upsert strategy for existing records.")
@click.option("--auto-publish", is_flag=True, help="Publish records after successful import.")
@click.option("--media-selector", type=str, help="Column/XPath for media filename mapping (objects only).")
@click.option("--dry-run", is_flag=True, help="Validate and print preview without importing.")
def import_csv(
    file: str,
    record_type: str,
    mapping: str,
    subtype: str | None,
    idno_strategy: str,
    upsert_strategy: str,
    auto_publish: bool,
    media_selector: str | None,
    dry_run: bool,
) -> None:
    """Import records from a CSV file using a JSON mapping."""
    import_csv_impl(
        file=file,
        record_type=record_type,
        mapping_path=mapping,
        subtype=subtype,
        idno_strategy=idno_strategy,
        upsert_strategy=upsert_strategy,
        auto_publish=auto_publish,
        media_selector=media_selector,
        dry_run=dry_run,
    )


@cli.command(name="import-xml")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=str))
@click.option("--type", "record_type", required=True, type=str, help="Record type: object, entity, place or occurrence.")
@click.option("--mapping", required=True, type=click.Path(exists=True, dir_okay=False, path_type=str), help="JSON mapping file.")
@click.option("--record-xpath", required=True, type=str, help="XPath selecting each record (Clark notation, e.g. '{http://...}mods').")
@click.option("--subtype", type=str, help="Record subtype.")
@click.option("--idno-strategy", default="auto", type=click.Choice(["auto", "column", "skip"]), help="ID number strategy.")
@click.option("--upsert-strategy", default="skip", type=click.Choice(["skip", "merge", "replace"]), help="Upsert strategy for existing records.")
@click.option("--auto-publish", is_flag=True, help="Publish records after successful import.")
@click.option("--media-selector", type=str, help="XPath for media filename mapping (objects only).")
@click.option("--dry-run", is_flag=True, help="Validate and print preview without importing.")
def import_xml(
    file: str,
    record_type: str,
    mapping: str,
    record_xpath: str,
    subtype: str | None,
    idno_strategy: str,
    upsert_strategy: str,
    auto_publish: bool,
    media_selector: str | None,
    dry_run: bool,
) -> None:
    """Import records from an XML file using a JSON mapping."""
    import_xml_impl(
        file=file,
        record_type=record_type,
        mapping_path=mapping,
        record_xpath=record_xpath,
        subtype=subtype,
        idno_strategy=idno_strategy,
        upsert_strategy=upsert_strategy,
        auto_publish=auto_publish,
        media_selector=media_selector,
        dry_run=dry_run,
    )


@cli.command(name="reset-admin")
def reset_admin() -> None:
    """Reset the admin/superuser password (interactive)."""
    reset_admin_impl()


def main() -> None:
    cli()
