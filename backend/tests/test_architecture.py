# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from pytest_archon import archrule


def test_core_does_not_import_services() -> None:
    """Core models and schemas must be independent of business services."""
    (
        archrule("core_does_not_import_services")
        .match("katalon.core*")
        .should_not_import("katalon.services*")
        .check("katalon")
    )


def test_core_does_not_import_api() -> None:
    """Core models and schemas must never depend on the HTTP API layer."""
    (
        archrule("core_does_not_import_api")
        .match("katalon.core*")
        .should_not_import("katalon.api*")
        .check("katalon")
    )


def test_core_does_not_import_workers() -> None:
    """Core models and schemas must not depend on Celery worker tasks.

    ``only_toplevel_imports=True``: database.py imports
    workers.enqueue lazily (function-local, inside get_db()) specifically to
    break this cycle while keeping the after-commit-hook dispatch (#392) —
    core*/services* consumers of database.py never see a module-level
    dependency on workers*. A module-level (toplevel) import would still be
    caught by this rule.
    """
    (
        archrule("core_does_not_import_workers")
        .match("katalon.core*")
        .should_not_import("katalon.workers*")
        .check("katalon", only_toplevel_imports=True)
    )


def test_services_do_not_import_api() -> None:
    """Service layer (business logic) must never depend on HTTP presentation (API routes)."""
    (
        archrule("services_do_not_import_api")
        .match("katalon.services*")
        .should_not_import("katalon.api*")
        .check("katalon")
    )


def test_integrations_do_not_import_api() -> None:
    """Integrations (ES, Cantaloupe, OAI-PMH, Authorities) must not depend on HTTP endpoints."""
    (
        archrule("integrations_do_not_import_api")
        .match("katalon.integrations*")
        .should_not_import("katalon.api*")
        .check("katalon")
    )


def test_workers_do_not_import_api() -> None:
    """Celery background tasks must use services/core and never depend on HTTP API routes."""
    (
        archrule("workers_do_not_import_api")
        .match("katalon.workers*")
        .should_not_import("katalon.api*")
        .check("katalon")
    )
