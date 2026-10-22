# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Container bootstrap, run once before Uvicorn starts its workers."""

import asyncio

from katalon.database import engine
from katalon.integrations.elasticsearch import close_es
from katalon.main import initialize_application


async def main() -> None:
    try:
        await initialize_application()
    finally:
        await close_es()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
