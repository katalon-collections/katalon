"""
Emergency admin password reset.

Usage:
    docker compose exec api python -m katalon.management.reset_admin
"""

from __future__ import annotations

import asyncio
import secrets
import sys
from pathlib import Path

RESET_CREDENTIALS_PATH = Path("/var/lib/katalon/reset-credentials.txt")
PASSWORD_TOKEN_BYTES = 15


async def _reset() -> None:
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

    if len(admins) > 1:
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

    new_password = secrets.token_urlsafe(PASSWORD_TOKEN_BYTES)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == target.id))
        user = result.scalar_one()
        user.hashed_password = hash_password(new_password)
        await db.commit()

    print()
    print("====== KATALON ADMIN RESET ======")
    print(f"Email:    {target.email}")
    print(f"Password: {new_password}")
    print("=================================")
    print()

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


def main() -> None:
    asyncio.run(_reset())


if __name__ == "__main__":
    main()
