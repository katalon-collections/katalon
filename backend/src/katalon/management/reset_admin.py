# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""
Emergency admin password reset.

Usage:
    katalon-manage reset-admin
    katalon-manage reset-admin --email admin@katalon.dev --password 1qayxsw2
"""

from __future__ import annotations

import asyncio
import secrets
import sys
from pathlib import Path

RESET_CREDENTIALS_PATH = Path("/var/lib/katalon/reset-credentials.txt")
PASSWORD_TOKEN_BYTES = 15


async def _reset(email: str | None = None, password: str | None = None) -> None:
    from sqlalchemy import select

    from katalon.api.v1.auth import hash_password
    from katalon.core.models import User
    from katalon.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.role.in_(("admin", "superuser")))
        )
        admins = result.scalars().all()

    if not admins:
        print("ERROR: No admin or superuser account found in the database.", file=sys.stderr)
        print("Run the API first so the first-run init creates an admin account.", file=sys.stderr)
        sys.exit(1)

    if email:
        target = next((admin for admin in admins if admin.email == email), None)
        if target is None:
            print(f"ERROR: No admin or superuser account found for {email}.", file=sys.stderr)
            sys.exit(1)
    elif len(admins) > 1:
        print("Multiple admin/superuser accounts found:")
        for i, u in enumerate(admins, 1):
            print(f"  [{i}] {u.email} (role: {u.role})")
        while True:
            choice = input("Which account to reset? Enter number: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(admins):
                target = admins[int(choice) - 1]
                break
            print("Invalid choice, try again.")
    else:
        target = admins[0]

    if password is not None and (
        len(password) < 8
        or not any(char.isalpha() for char in password)
        or not any(char.isdigit() for char in password)
    ):
        raise ValueError("Password must have at least eight characters, letters, and digits.")

    new_password = password or secrets.token_urlsafe(PASSWORD_TOKEN_BYTES)


    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == target.id))
        user = result.scalar_one()
        user.hashed_password = hash_password(new_password)
        await db.commit()

    print()
    print("====== KATALON ADMIN RESET ======")
    print(f"Email:    {target.email}")
    if password is None:
        print(f"Password: {new_password}")
    else:
        print("Password: supplied via --password")
    print("=================================")
    print()

    if password is not None:
        return

    try:
        RESET_CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESET_CREDENTIALS_PATH.write_text(
            "\n".join([
                "====== KATALON ADMIN RESET ======",
                f"Email:    {target.email}",
                f"Password: {new_password}",
                "Change this password after first login.",
                "",
            ]),
            encoding="utf-8",
        )
        RESET_CREDENTIALS_PATH.chmod(0o600)
        print(f"Credentials also written to: {RESET_CREDENTIALS_PATH}")
    except OSError as exc:
        print(f"Could not write credentials file: {exc}", file=sys.stderr)


def reset_admin(email: str | None = None, password: str | None = None) -> None:
    """Reset an admin/superuser password."""
    asyncio.run(_reset(email=email, password=password))


def main() -> None:
    reset_admin()


if __name__ == "__main__":
    main()
