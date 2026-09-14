# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Issue #388: the global audit log must require the `audit_log` feature and
must filter entries (and relation-partner labels/ids embedded in a diff) down
to record types the caller may read. Per-record `.../audit-log` endpoints
must require read permission on that specific record.

All 7 core record types (object, entity, place, occurrence, procedure,
collection, storage_location) are covered across global audit log filtering,
record-specific audit endpoints, and relation diff scrubbing.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest


async def _create_role_user(
    async_client, auth_headers: dict[str, str], role: str
) -> dict[str, str]:
    email = f"{role}-{uuid.uuid4().hex[:10]}@katalon.dev"
    password = "Test1234"
    created = await async_client.post(
        "/v1/users",
        headers=auth_headers,
        json={"email": email, "password": password, "role": role},
    )
    assert created.status_code == 201, created.text
    token = (
        await async_client.post(
            "/v1/auth/token",
            data={"username": email, "password": password},
        )
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@asynccontextmanager
async def _without_read_permission(
    async_client, auth_headers: dict[str, str], role: str, record_type: str
) -> AsyncIterator[None]:
    """Temporarily revoke read permission for a role and record type.

    `role_permissions` is global, shared-session state across the integration
    test run; we must always restore the original permissions in `finally`.
    """
    perms_res = await async_client.get("/v1/users/permissions", headers=auth_headers)
    assert perms_res.status_code == 200, perms_res.text
    original_role_perms = [
        {"role": p["role"], "record_type": p["record_type"], "action": p["action"]}
        for p in perms_res.json()
        if p["role"] == role
    ]
    reduced_perms = [
        p
        for p in original_role_perms
        if not (p["record_type"] == record_type and p["action"] == "read")
    ]
    update_res = await async_client.put(
        f"/v1/users/permissions/{role}",
        headers=auth_headers,
        json={"permissions": reduced_perms},
    )
    assert update_res.status_code == 200, update_res.text
    try:
        yield
    finally:
        restore_res = await async_client.put(
            f"/v1/users/permissions/{role}",
            headers=auth_headers,
            json={"permissions": original_role_perms},
        )
        assert restore_res.status_code == 200, restore_res.text


async def _create_record(
    async_client, auth_headers: dict[str, str], record_type: str, label: str
) -> tuple[str, str]:
    """Create a record of any of the 7 core record types and return (record_id, idno)."""
    uid = uuid.uuid4().hex[:12]
    if record_type == "procedure":
        idno = f"PRO-{uid}"
        res = await async_client.post(
            "/v1/procedures",
            headers=auth_headers,
            json={
                "idno": idno,
                "procedure_type": "conservation",
                "status": "draft",
                "metadata_": {"label": label},
            },
        )
    elif record_type == "storage_location":
        idno = f"LOC-{uid}"
        res = await async_client.post(
            "/v1/storage-locations",
            headers=auth_headers,
            json={
                "idno": idno,
                "metadata_": {"label": label, "idno": idno},
            },
        )
    else:
        prefix = record_type[:3].upper()
        idno = f"{prefix}-{uid}"
        route = "entities" if record_type == "entity" else f"{record_type}s"
        res = await async_client.post(
            f"/v1/{route}",
            headers=auth_headers,
            json={
                "idno": idno,
                "status": "draft",
                "metadata_": {"label": label},
            },
        )
    assert res.status_code == 201, res.text
    return res.json()["id"], idno


async def _create_procedure(
    async_client, auth_headers: dict[str, str], label: str
) -> tuple[str, str]:
    return await _create_record(async_client, auth_headers, "procedure", label)


# ===========================================================================
# 1. Authentication requirements
# ===========================================================================


@pytest.mark.asyncio
async def test_audit_endpoints_require_authentication(async_client, auth_headers) -> None:
    procedure_id, _ = await _create_procedure(async_client, auth_headers, "Anon-Test")
    assert (await async_client.get("/v1/audit")).status_code == 401
    assert (await async_client.get("/v1/audit/search")).status_code == 401
    assert (await async_client.get(f"/v1/procedures/{procedure_id}/audit-log")).status_code == 401


@pytest.mark.parametrize(
    ("record_type", "route"),
    [
        ("object", "objects"),
        ("entity", "entities"),
        ("place", "places"),
        ("occurrence", "occurrences"),
        ("collection", "collections"),
        ("procedure", "procedures"),
        ("storage_location", "storage-locations"),
    ],
)
@pytest.mark.asyncio
async def test_record_audit_log_endpoint_requires_authentication(
    async_client, auth_headers, record_type: str, route: str
) -> None:
    record_id, _ = await _create_record(async_client, auth_headers, record_type, "Anon-Route-Test")
    res = await async_client.get(f"/v1/{route}/{record_id}/audit-log")
    assert res.status_code == 401


# ===========================================================================
# 2. Global audit log (/v1/audit and /v1/audit/search) authorization
# ===========================================================================


@pytest.mark.parametrize("record_type", ["procedure", "storage_location"])
@pytest.mark.asyncio
async def test_viewer_never_sees_unreadable_default_types_in_global_log(
    async_client, auth_headers, record_type: str
) -> None:
    """Viewer holds the `audit_log` feature by default but never gets read
    permission for `procedure` or `storage_location` (denied by definition).
    The feature must not bypass the record-type filter in /v1/audit or
    /v1/audit/search."""
    record_id, _ = await _create_record(
        async_client, auth_headers, record_type, f"Viewer-Filter-{record_type}"
    )
    viewer_headers = await _create_role_user(async_client, auth_headers, "viewer")

    list_res = await async_client.get(
        "/v1/audit",
        headers=viewer_headers,
        params={"record_type": record_type, "record_id": record_id},
    )
    assert list_res.status_code == 200
    assert list_res.json() == []

    search_res = await async_client.get(
        "/v1/audit/search",
        headers=viewer_headers,
        params={"record_type": record_type, "record_id": record_id},
    )
    assert search_res.status_code == 200
    assert search_res.json()["items"] == []
    assert search_res.json()["total"] == 0


@pytest.mark.parametrize("record_type", ["procedure", "storage_location"])
@pytest.mark.asyncio
async def test_cataloger_sees_unreadable_default_types_in_global_log(
    async_client, auth_headers, record_type: str
) -> None:
    """Cataloger holds read permission on procedure and storage_location and
    must see their audit entries in both /v1/audit and /v1/audit/search."""
    record_id, _ = await _create_record(
        async_client, auth_headers, record_type, f"Cataloger-Filter-{record_type}"
    )
    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    list_res = await async_client.get(
        "/v1/audit",
        headers=cataloger_headers,
        params={"record_type": record_type, "record_id": record_id},
    )
    assert list_res.status_code == 200
    assert any(entry["action"] == "create" for entry in list_res.json())

    search_res = await async_client.get(
        "/v1/audit/search",
        headers=cataloger_headers,
        params={"record_type": record_type, "record_id": record_id},
    )
    assert search_res.status_code == 200
    assert search_res.json()["total"] >= 1


@pytest.mark.parametrize("record_type", ["object", "entity", "place", "occurrence", "collection"])
@pytest.mark.asyncio
async def test_global_audit_log_filters_out_types_without_read_permission(
    async_client, auth_headers, record_type: str
) -> None:
    """When a user role lacks read permission for a configurable record type
    (e.g. via temporarily revoked role permission), entries of that type must
    NOT appear in /v1/audit or /v1/audit/search."""
    record_id, _ = await _create_record(
        async_client, auth_headers, record_type, f"Filter-Test-{record_type}"
    )
    viewer_headers = await _create_role_user(async_client, auth_headers, "viewer")
    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    async with _without_read_permission(async_client, auth_headers, "viewer", record_type):
        list_res = await async_client.get(
            "/v1/audit",
            headers=viewer_headers,
            params={"record_type": record_type, "record_id": record_id},
        )
        assert list_res.status_code == 200
        assert list_res.json() == []

        search_res = await async_client.get(
            "/v1/audit/search",
            headers=viewer_headers,
            params={"record_type": record_type, "record_id": record_id},
        )
        assert search_res.status_code == 200
        assert search_res.json()["items"] == []
        assert search_res.json()["total"] == 0

        # Cataloger with read permission sees the entries
        cat_list = await async_client.get(
            "/v1/audit",
            headers=cataloger_headers,
            params={"record_type": record_type, "record_id": record_id},
        )
        assert cat_list.status_code == 200
        assert any(entry["action"] == "create" for entry in cat_list.json())

        cat_search = await async_client.get(
            "/v1/audit/search",
            headers=cataloger_headers,
            params={"record_type": record_type, "record_id": record_id},
        )
        assert cat_search.status_code == 200
        assert cat_search.json()["total"] >= 1

    # Once permission is restored, viewer with read permission sees entries
    restored_res = await async_client.get(
        "/v1/audit",
        headers=viewer_headers,
        params={"record_type": record_type, "record_id": record_id},
    )
    assert restored_res.status_code == 200
    assert any(entry["action"] == "create" for entry in restored_res.json())


# ===========================================================================
# 3. Record-specific audit log endpoints
# ===========================================================================


@pytest.mark.asyncio
async def test_procedure_audit_log_endpoint_requires_procedure_read(
    async_client, auth_headers
) -> None:
    procedure_id, _ = await _create_procedure(async_client, auth_headers, "Sub-Route-Test")

    viewer_headers = await _create_role_user(async_client, auth_headers, "viewer")
    assert (
        await async_client.get(f"/v1/procedures/{procedure_id}/audit-log", headers=viewer_headers)
    ).status_code == 403

    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")
    ok_res = await async_client.get(
        f"/v1/procedures/{procedure_id}/audit-log", headers=cataloger_headers
    )
    assert ok_res.status_code == 200
    assert any(entry["action"] == "create" for entry in ok_res.json())


@pytest.mark.parametrize(
    ("record_type", "route"),
    [
        ("object", "objects"),
        ("entity", "entities"),
        ("place", "places"),
        ("occurrence", "occurrences"),
        ("collection", "collections"),
    ],
)
@pytest.mark.asyncio
async def test_record_audit_log_endpoint_requires_read_permission(
    async_client, auth_headers, record_type: str, route: str
) -> None:
    """The /v1/{type}s/{id}/audit-log endpoints for object, entity, place,
    occurrence, and collection must require read permission on that record type (403)."""
    record_id, _ = await _create_record(
        async_client, auth_headers, record_type, f"Audit-Route-{record_type}"
    )

    viewer_headers = await _create_role_user(async_client, auth_headers, "viewer")
    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    async with _without_read_permission(async_client, auth_headers, "viewer", record_type):
        denied_res = await async_client.get(
            f"/v1/{route}/{record_id}/audit-log", headers=viewer_headers
        )
        assert denied_res.status_code == 403, denied_res.text

        allowed_res = await async_client.get(
            f"/v1/{route}/{record_id}/audit-log", headers=cataloger_headers
        )
        assert allowed_res.status_code == 200, allowed_res.text
        assert any(entry["action"] == "create" for entry in allowed_res.json())

    # Once permission is restored, viewer also gets 200 OK
    restored_res = await async_client.get(
        f"/v1/{route}/{record_id}/audit-log", headers=viewer_headers
    )
    assert restored_res.status_code == 200
    assert any(entry["action"] == "create" for entry in restored_res.json())


@pytest.mark.asyncio
async def test_storage_location_audit_log_enforces_read_permission(
    async_client, auth_headers
) -> None:
    """Direct /v1/storage-locations/{id}/audit-log and global /v1/audit?record_type=storage_location
    enforce storage_location:read permission: viewers (no read access) get 403 on the sub-route
    and 0 hits on the global log, while authorized users (cataloger) receive the entries."""
    loc_id, _ = await _create_record(
        async_client, auth_headers, "storage_location", "Lager-Audit-Test"
    )

    viewer_headers = await _create_role_user(async_client, auth_headers, "viewer")
    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    # 1. Direct route /v1/storage-locations/{id}/audit-log requires authentication (401)
    anon_route = await async_client.get(f"/v1/storage-locations/{loc_id}/audit-log")
    assert anon_route.status_code == 401

    # 2. Viewer (no storage_location:read) -> 403 on direct sub-route
    viewer_sub = await async_client.get(
        f"/v1/storage-locations/{loc_id}/audit-log", headers=viewer_headers
    )
    assert viewer_sub.status_code == 403

    # 3. Cataloger (has storage_location:read) -> 200 on direct sub-route
    cataloger_sub = await async_client.get(
        f"/v1/storage-locations/{loc_id}/audit-log", headers=cataloger_headers
    )
    assert cataloger_sub.status_code == 200
    assert any(entry["action"] == "create" for entry in cataloger_sub.json())

    # 4. Viewer uses the frontend pattern via /v1/audit -> 0 hits due to missing read right
    viewer_res = await async_client.get(
        "/v1/audit",
        headers=viewer_headers,
        params={"record_type": "storage_location", "record_id": loc_id},
    )
    assert viewer_res.status_code == 200
    assert viewer_res.json() == []

    # 5. Cataloger has storage_location:read -> receives audit entries via /v1/audit
    cataloger_res = await async_client.get(
        "/v1/audit",
        headers=cataloger_headers,
        params={"record_type": "storage_location", "record_id": loc_id},
    )
    assert cataloger_res.status_code == 200
    entries = cataloger_res.json()
    assert any(entry["action"] == "create" for entry in entries)


# ===========================================================================
# 4. Scrubbing unreadable relation references (_scrub_unreadable_related)
# ===========================================================================


@pytest.mark.asyncio
async def test_object_audit_log_scrubs_related_label_for_unreadable_procedure(
    async_client, auth_headers
) -> None:
    object_id, _ = await _create_record(async_client, auth_headers, "object", "Kiste")
    procedure_id, procedure_idno = await _create_procedure(
        async_client, auth_headers, "Related-Scrub-Procedure"
    )

    relation_res = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": object_id,
            "to_type": "procedure",
            "to_id": procedure_id,
            "relation_type": "concerns",
            "metadata_": {},
        },
    )
    assert relation_res.status_code == 201, relation_res.text

    # Viewer can read the object (and thus its audit log), but not the
    # related procedure — the relation-partner id/type/label must be
    # stripped from the diff, not just left with a None label.
    viewer_headers = await _create_role_user(async_client, auth_headers, "viewer")
    viewer_log = await async_client.get(
        f"/v1/objects/{object_id}/audit-log", headers=viewer_headers
    )
    assert viewer_log.status_code == 200
    relation_entries = [e for e in viewer_log.json() if e["action"] == "relation_add"]
    assert relation_entries, "expected a relation_add audit entry"
    for entry in relation_entries:
        fields = entry["changed_fields"]
        assert "related_record_id" not in fields
        assert "related_record_type" not in fields
        assert "related_record_label" not in fields

    # Cataloger can read both object and procedure — the related label must
    # be resolved and present.
    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")
    cataloger_log = await async_client.get(
        f"/v1/objects/{object_id}/audit-log", headers=cataloger_headers
    )
    assert cataloger_log.status_code == 200
    relation_entries = [e for e in cataloger_log.json() if e["action"] == "relation_add"]
    assert relation_entries
    assert any(
        e["changed_fields"].get("related_record_label") == procedure_idno for e in relation_entries
    )


@pytest.mark.asyncio
async def test_object_audit_log_scrubs_related_label_for_unreadable_storage_location(
    async_client, auth_headers
) -> None:
    """When an object has a relation to a storage_location, a viewer (who cannot
    read storage_location) must see the relation_add audit entry on the object
    with related_record_id/type/label scrubbed. A cataloger (who can read both)
    must see the fully resolved storage_location label."""
    object_id, _ = await _create_record(async_client, auth_headers, "object", "Sammelbox")
    loc_id, loc_idno = await _create_record(
        async_client, auth_headers, "storage_location", "Hauptarchiv Regal 4"
    )

    relation_res = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": object_id,
            "to_type": "storage_location",
            "to_id": loc_id,
            "relation_type": "located_at",
            "metadata_": {},
        },
    )
    assert relation_res.status_code == 201, relation_res.text

    viewer_headers = await _create_role_user(async_client, auth_headers, "viewer")
    viewer_log = await async_client.get(
        f"/v1/objects/{object_id}/audit-log", headers=viewer_headers
    )
    assert viewer_log.status_code == 200
    relation_entries = [e for e in viewer_log.json() if e["action"] == "relation_add"]
    assert relation_entries, "expected a relation_add audit entry"
    for entry in relation_entries:
        fields = entry["changed_fields"]
        assert "related_record_id" not in fields
        assert "related_record_type" not in fields
        assert "related_record_label" not in fields

    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")
    cataloger_log = await async_client.get(
        f"/v1/objects/{object_id}/audit-log", headers=cataloger_headers
    )
    assert cataloger_log.status_code == 200
    relation_entries = [e for e in cataloger_log.json() if e["action"] == "relation_add"]
    assert relation_entries
    assert any(
        loc_idno in str(e["changed_fields"].get("related_record_label")) for e in relation_entries
    )


@pytest.mark.asyncio
async def test_global_audit_log_scrubs_unreadable_relation_diff(async_client, auth_headers) -> None:
    """Scrubbing must also occur when relation_add entries are fetched through
    the global /v1/audit endpoint."""
    object_id, _ = await _create_record(async_client, auth_headers, "object", "Rel-Global-Object")
    loc_id, loc_idno = await _create_record(
        async_client, auth_headers, "storage_location", "Lager-Global"
    )

    relation_res = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": object_id,
            "to_type": "storage_location",
            "to_id": loc_id,
            "relation_type": "located_at",
            "metadata_": {},
        },
    )
    assert relation_res.status_code == 201, relation_res.text

    # Global log queried by viewer
    viewer_headers = await _create_role_user(async_client, auth_headers, "viewer")
    viewer_res = await async_client.get(
        "/v1/audit",
        headers=viewer_headers,
        params={"record_type": "object", "record_id": object_id},
    )
    assert viewer_res.status_code == 200
    rel_entries = [e for e in viewer_res.json() if e["action"] == "relation_add"]
    assert rel_entries
    for entry in rel_entries:
        fields = entry["changed_fields"]
        assert "related_record_id" not in fields
        assert "related_record_type" not in fields
        assert "related_record_label" not in fields

    # Global log queried by cataloger
    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")
    cataloger_res = await async_client.get(
        "/v1/audit",
        headers=cataloger_headers,
        params={"record_type": "object", "record_id": object_id},
    )
    assert cataloger_res.status_code == 200
    cat_rel_entries = [e for e in cataloger_res.json() if e["action"] == "relation_add"]
    assert cat_rel_entries
    assert any(
        loc_idno in str(e["changed_fields"].get("related_record_label")) for e in cat_rel_entries
    )


@pytest.mark.asyncio
async def test_object_audit_log_scrubs_related_label_when_permission_dynamically_revoked(
    async_client, auth_headers
) -> None:
    """When a relation targets a type that is normally readable (e.g. entity),
    but the user's read permission on that type is revoked, the relation diff
    in the audit log must dynamically scrub the related fields."""
    object_id, _ = await _create_record(async_client, auth_headers, "object", "Gemälde")
    entity_id, entity_idno = await _create_record(
        async_client, auth_headers, "entity", "Albrecht Dürer"
    )

    relation_res = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": object_id,
            "to_type": "entity",
            "to_id": entity_id,
            "relation_type": "depicts",
            "metadata_": {},
        },
    )
    assert relation_res.status_code == 201, relation_res.text

    viewer_headers = await _create_role_user(async_client, auth_headers, "viewer")
    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    # With entity:read revoked for viewer
    async with _without_read_permission(async_client, auth_headers, "viewer", "entity"):
        viewer_log = await async_client.get(
            f"/v1/objects/{object_id}/audit-log", headers=viewer_headers
        )
        assert viewer_log.status_code == 200
        rel_entries = [e for e in viewer_log.json() if e["action"] == "relation_add"]
        assert rel_entries
        for entry in rel_entries:
            fields = entry["changed_fields"]
            assert "related_record_id" not in fields
            assert "related_record_type" not in fields
            assert "related_record_label" not in fields

        # Cataloger still sees the label
        cat_log = await async_client.get(
            f"/v1/objects/{object_id}/audit-log", headers=cataloger_headers
        )
        assert cat_log.status_code == 200
        cat_entries = [e for e in cat_log.json() if e["action"] == "relation_add"]
        assert cat_entries
        assert any(
            entity_idno in str(e["changed_fields"].get("related_record_label")) for e in cat_entries
        )

    # After restoration, viewer sees the label too
    restored_log = await async_client.get(
        f"/v1/objects/{object_id}/audit-log", headers=viewer_headers
    )
    assert restored_log.status_code == 200
    restored_entries = [e for e in restored_log.json() if e["action"] == "relation_add"]
    assert restored_entries
    assert any(
        entity_idno in str(e["changed_fields"].get("related_record_label"))
        for e in restored_entries
    )
