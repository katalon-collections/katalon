# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from katalon.services.search_service import search_admin_data


class _Result:
    def __init__(self, values: list[object], *, tuples: bool = False) -> None:
        self.values = values
        self.tuples = tuples

    def all(self) -> list[object]:
        return self.values

    def scalars(self) -> _Result:
        return self


class _Db:
    def __init__(self) -> None:
        self.calls = 0
        self.user_id = uuid4()

    async def execute(self, _statement: object) -> _Result:
        self.calls += 1
        if self.calls == 2:
            return _Result([SimpleNamespace(id=self.user_id, email="search@example.org", role="editor")])
        return _Result([])


@pytest.mark.asyncio
async def test_admin_search_returns_user_result() -> None:
    db = _Db()
    items = await search_admin_data(db, "search")  # type: ignore[arg-type]

    assert len(items) == 1
    assert items[0] == {
        "id": str(db.user_id), "kind": "user", "title": "search@example.org",
        "subtitle": "editor", "route": "users", "edit_id": None,
    }
