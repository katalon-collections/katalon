# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Management CLI for Katalon development and operations.

Commands:
    katalon-manage db-reset
    katalon-manage import-csv
    katalon-manage import-xml
    katalon-manage reset-admin
    katalon-manage warm-thumbnails
    katalon-manage reindex [--type <type>] [--sync | --status]
    katalon-manage lido-report
    katalon-manage resync-schema-relations
    katalon-manage attachments-gc --older-than 7d [--dry-run]
"""

from __future__ import annotations

from importlib.metadata import version as get_version

import click

from katalon.management.create_user import create_user as create_user_impl
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
@click.option("--email", type=str, help="Admin or superuser email to reset.")
@click.option("--password", help="Explicit new password; otherwise a random password is generated.")
def reset_admin(email: str | None, password: str | None) -> None:
    """Reset an admin/superuser password."""
    reset_admin_impl(email=email, password=password)


@cli.command(name="create-user")
@click.option("--email", required=True, help="Email address for the new user.")
@click.password_option(confirmation_prompt=True)
@click.option(
    "--role",
    required=True,
    type=click.Choice(["admin", "editor", "cataloger", "viewer"]),
    help="Role for the new user.",
)
def create_user(email: str, password: str, role: str) -> None:
    """Create a user."""
    try:
        create_user_impl(email=email, password=password, role=role)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Created user {email} with role {role}.")

def main() -> None:
    cli()


@cli.command(name="warm-thumbnails")
@click.option("--primary-only", is_flag=True, help="Only the primary image of each object.")
@click.option("--restart", is_flag=True, help="Start over instead of resuming an interrupted run.")
@click.option("--status", "show_status", is_flag=True, help="Only show the progress of the current run.")
def warm_thumbnails(primary_only: bool, restart: bool, show_status: bool) -> None:
    """Pre-render portal thumbnails in Cantaloupe's cache (runs in the worker).

    Primary images first, then the rest; batches run one after another with
    THUMBNAIL_WARM_CONCURRENCY parallel requests. Re-running resumes an
    interrupted run; a running one is not started twice.
    """
    from katalon.workers.thumbnail_tasks import bulk_status, start_bulk_sync

    state = bulk_status() if show_status else start_bulk_sync(primary_only=primary_only, restart=restart)
    if not state.get("phase"):
        click.echo("Kein Vorwärm-Lauf bekannt.")
        return
    total = state.get("total") or 0
    done = state.get("done", 0) + state.get("failed", 0)
    phase = {"primary": "Hauptbilder", "rest": "weitere Bilder", "done": "fertig"}.get(state["phase"], state["phase"])
    running = "läuft" if state.get("running") else "angehalten" if state["phase"] != "done" else "abgeschlossen"
    click.echo(f"Vorschaubilder: {done}/{total} ({phase}, {running}); Fehler: {state.get('failed', 0)}")


@cli.command(name="lido-report")
@click.option("--mapping-set", "mapping_set_id", required=True, help="ID of the export mapping set.")
@click.option(
    "--output", "output", type=click.Path(dir_okay=False, writable=True), default=None,
    help="Write the CSV to this file instead of stdout.",
)
def lido_report(mapping_set_id: str, output: str | None) -> None:
    """Check all public records against a mapping set (required fields, rights checks).

    Prints the number of affected records per problem to stderr and one CSV row
    per problem (lidoRecID, record ID, message).
    """
    import asyncio
    import csv
    import sys
    import uuid
    from contextlib import nullcontext

    from katalon.database import AsyncSessionLocal
    from katalon.services.export_report_service import ExportReport, build_report

    async def _build() -> ExportReport:
        async with AsyncSessionLocal() as db:
            return await build_report(db, uuid.UUID(mapping_set_id))

    try:
        report = asyncio.run(_build())
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Geprüft: {report.checked}, mit Fehlern: {len(report.problems)}", err=True)
    for kind, count in report.counts().most_common():
        click.echo(f"  {count:>6}  {kind}", err=True)
    target = open(output, "w", newline="", encoding="utf-8") if output else nullcontext(sys.stdout)  # noqa: SIM115
    with target as handle:
        writer = csv.writer(handle)
        writer.writerow(["lidoRecID", "record_id", "fehler"])
        for problem in report.problems:
            for message in problem.messages:
                writer.writerow([problem.rec_id, problem.record_id, message])


@cli.command(name="resync-schema-relations")
@click.option("--dry-run", is_flag=True, help="Only report duplicate relation rows; write nothing.")
def resync_schema_relations(dry_run: bool) -> None:
    """Rebuild the schema-derived relation rows of all records.

    Removes duplicates that older versions created for equally named relation fields of
    different subtypes. Without --dry-run this changes data: back up first and run it on an
    instance only with the operator's approval.
    """
    from katalon.management.resync_relations import run

    report = run(dry_run)
    click.echo(
        f"Doppelte schema-abgeleitete Relationszeilen vorher: {report.extra_rows} überzählig "
        f"in {report.duplicate_groups} Gruppen."
    )
    if dry_run:
        click.echo(f"Trockenlauf: {report.records} Datensätze würden neu synchronisiert, nichts geschrieben.")
    else:
        click.echo(f"{report.resynced} von {report.records} Datensätzen neu synchronisiert.")
        click.echo(f"Überzählige Zeilen danach: {report.extra_rows_after}.")


@cli.command(name="attachments-gc")
@click.option(
    "--older-than",
    default="7d",
    show_default=True,
    help="Only consider attachments created before this age: '<n>d', '<n>h' or '0' (no age limit).",
)
@click.option("--dry-run", is_flag=True, help="Count what would be deleted; delete nothing.")
def attachments_gc(older_than: str, dry_run: bool) -> None:
    """Delete unreferenced `file` attachments (rows and stored files).

    An attachment is kept while its id appears in the current metadata of its record
    (trashed records included) or in one of that record's snapshots. Attachments whose
    record no longer exists are deleted. Run `--older-than 0` only after removing a file
    from its field and deleting any snapshot that still contains it.
    """
    import asyncio

    from katalon.database import AsyncSessionLocal
    from katalon.services.attachment_service import gc_attachments, parse_older_than

    try:
        age = parse_older_than(older_than)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="--older-than") from exc

    async def _run() -> dict[str, int]:
        async with AsyncSessionLocal() as db:
            return await gc_attachments(db, older_than=age, dry_run=dry_run)

    report = asyncio.run(_run())
    click.echo(
        f"Anhänge älter als {older_than}: {report['candidates']}; "
        f"referenziert: {report['referenced']}; verwaist: {report['orphaned']}."
    )
    if dry_run:
        click.echo(f"Trockenlauf: {report['deleted']} würden gelöscht, nichts geschrieben.")
    else:
        click.echo(f"Gelöscht: {report['deleted']}; Speicherfehler (Zeile bleibt): {report['failed']}.")


@cli.command(name="reindex")
@click.option(
    "--type",
    "target_type",
    type=click.Choice(
        ["object", "entity", "place", "occurrence", "procedure", "collection", "storage_location"]
    ),
    default=None,
    help="Rebuild only this record type instead of a full index rebuild.",
)
@click.option(
    "--sync",
    is_flag=True,
    help="Run the rebuild synchronously in this process instead of queueing it for the worker.",
)
@click.option(
    "--status",
    "show_status",
    is_flag=True,
    help="Show current reindex progress without starting a rebuild.",
)
def reindex(target_type: str | None, sync: bool, show_status: bool) -> None:
    """Trigger or inspect a search index rebuild without needing an Admin login."""
    if sync and show_status:
        raise click.UsageError("--sync und --status können nicht kombiniert werden.")

    from katalon.core.schemas import RECORD_TYPES
    from katalon.workers import index_tasks, reindex_state

    if show_status:
        state = reindex_state.read_status(sorted(RECORD_TYPES))
        shown = False
        for name in [reindex_state.FULL, *sorted(RECORD_TYPES)]:
            entry = state.get(name) or {}
            prog = entry.get("progress") or {}
            if not prog and not entry.get("queued") and not entry.get("dirty"):
                continue
            shown = True
            label = "gesamt" if name == reindex_state.FULL else name
            run_state = prog.get("state") or ("wartend" if entry.get("queued") else "ausstehend")
            built = prog.get("built", "0")
            total = prog.get("total", "0")
            click.echo(f"{label}: {run_state} ({built}/{total})")
        if not shown:
            click.echo("Kein Reindex-Lauf bekannt.")
        return

    if sync:
        if target_type:
            report = index_tasks.bulk_reindex_type_task.run(target_type)
            click.echo(
                f"Reindex '{target_type}': {report.get('status')} "
                f"(indiziert: {report.get('indexed', 0)}, entfernt: {report.get('removed', 0)})."
            )
        else:
            report = index_tasks.reindex_all_task.run()
            click.echo(
                f"Komplett-Reindex: {report.get('status')} "
                f"(Index: {report.get('index', '-')})."
            )
        return

    if target_type:
        enqueued = reindex_state.request_bulk_reindex(target_type, strict=False)
        msg = (
            f"Reindex für '{target_type}' eingereiht."
            if enqueued
            else f"Reindex für '{target_type}' ist bereits eingereiht oder vorgemerkt."
        )
        click.echo(msg)
    else:
        enqueued = reindex_state.request_full_rebuild(strict=False)
        msg = (
            "Komplett-Reindex eingereiht."
            if enqueued
            else "Komplett-Reindex ist bereits eingereiht oder vorgemerkt."
        )
        click.echo(msg)
