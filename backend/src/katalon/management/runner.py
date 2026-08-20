"""Console-script launcher for the management CLI.

Imports the CLI lazily so that a missing KATALON_SECRETS_KEY produces a
single, readable error message instead of a stack trace.
"""

from __future__ import annotations

import sys

import click

from katalon.errors import KatalonSecretsKeyError


def launcher() -> None:
    try:
        from katalon.management.cli import cli
    except KatalonSecretsKeyError as exc:
        click.echo(f"Fehler: {exc}", err=True)
        sys.exit(1)
    cli()
