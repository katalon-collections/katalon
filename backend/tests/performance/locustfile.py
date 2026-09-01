# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Locust performance tests for Katalon.

Run locally against the dev stack (api on localhost:8000 or via nginx on 80):

    cd backend
    KATALON_LOCUST_HOST=http://localhost:8000 \
    KATALON_LOCUST_EMAIL=admin@example.org \
    KATALON_LOCUST_PASSWORD=... \
        uv run locust -f tests/performance/locustfile.py

Then open http://localhost:8089 and start a swarm.
"""

from __future__ import annotations

import os
import random
import uuid
from typing import Any

from locust import HttpUser, between, task  # type: ignore[import-untyped]


def _default_host() -> str:
    return os.getenv("KATALON_LOCUST_HOST", "http://localhost:8000")


class PublicPortalUser(HttpUser):
    """Unauthenticated public-portal traffic."""

    host = _default_host()
    wait_time = between(1, 4)
    weight = 4

    def on_start(self) -> None:
        self.client.get("/health", name="/health")

    @task(5)
    def search(self) -> None:
        self.client.get("/portal/v1/search?q=marrakesch", name="/portal/v1/search")

    @task(3)
    def list_objects(self) -> None:
        self.client.get("/portal/v1/objects?page=1", name="/portal/v1/objects")

    @task(2)
    def portal_config(self) -> None:
        self.client.get("/portal/v1/portal/config", name="/portal/v1/portal/config")

    @task(2)
    def list_pages(self) -> None:
        self.client.get("/portal/v1/pages", name="/portal/v1/pages")

    @task(1)
    def get_object(self) -> None:
        # A fixed UUID is enough to exercise the path; most instances return 404.
        with self.client.get(
            f"/portal/v1/objects/{uuid.uuid4()}",
            name="/portal/v1/objects/{id}",
            catch_response=True,
        ) as response:
            if response.status_code == 404:
                response.success()


class AdminUser(HttpUser):
    """Authenticated admin/cataloguing traffic."""

    host = _default_host()
    wait_time = between(2, 6)
    weight = 1

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.access_token: str | None = None

    def on_start(self) -> None:
        email = os.getenv("KATALON_LOCUST_EMAIL", "admin@example.org")
        password = os.getenv("KATALON_LOCUST_PASSWORD", "")
        response = self.client.post(
            "/v1/auth/token",
            data={"username": email, "password": password, "grant_type": "password"},
            name="/v1/auth/token",
        )
        if response.status_code == 200:
            self.access_token = response.json().get("access_token")
        else:
            self.access_token = None

    def _headers(self) -> dict[str, str]:
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    @task(4)
    def list_schema(self) -> None:
        self.client.get(
            "/v1/schema/object",
            headers=self._headers(),
            name="/v1/schema/{type}",
        )

    @task(3)
    def list_objects(self) -> None:
        self.client.get("/v1/objects", headers=self._headers(), name="/v1/objects")

    @task(2)
    def list_entities(self) -> None:
        self.client.get("/v1/entities", headers=self._headers(), name="/v1/entities")

    @task(2)
    def list_vocabularies(self) -> None:
        self.client.get(
            "/v1/vocabularies",
            headers=self._headers(),
            name="/v1/vocabularies",
        )

    @task(1)
    def create_and_get_object(self) -> None:
        payload: dict[str, Any] = {
            "label": f"Locust test {uuid.uuid4()}",
            "idno": f"LOC-{random.randint(100000, 999999)}",
        }
        response = self.client.post(
            "/v1/objects",
            json=payload,
            headers=self._headers(),
            name="POST /v1/objects",
        )
        if response.status_code == 201:
            object_id = response.json().get("id")
            if object_id:
                self.client.get(
                    f"/v1/objects/{object_id}",
                    headers=self._headers(),
                    name="/v1/objects/{id}",
                )

    @task(1)
    def search_admin(self) -> None:
        self.client.get(
            "/v1/search?q=test",
            headers=self._headers(),
            name="/v1/search",
        )
