import uuid

import pytest

from katalon.core.models import MediaFile


@pytest.mark.asyncio
async def test_authenticated_api_resources_include_navigation_links(async_client, auth_headers) -> None:
    created_records = {}
    for path, record_type, payload in (
        ("objects", "object", {"object_type": None}),
        ("entities", "entity", {"entity_type": None}),
        ("places", "place", {"place_type": None}),
        ("occurrences", "occurrence", {"occurrence_type": None}),
    ):
        response = await async_client.post(
            f"/v1/{path}",
            headers=auth_headers,
            json={"idno": f"LINK-{uuid.uuid4().hex}", "status": "draft", "metadata_": {}, **payload},
        )
        assert response.status_code == 201, response.text
        record = response.json()
        created_records[path] = record["id"]
        assert record["_links"]["self"]["href"] == f"/v1/{path}/{record['id']}"
        assert record["_links"]["relations"]["href"] == (
            f"/v1/relations?from_type={record_type}"
            f"&from_id={record['id']}"
        )

    assert created_records["objects"]
    object_response = await async_client.get(
        f"/v1/objects/{created_records['objects']}", headers=auth_headers
    )
    assert object_response.json()["_links"]["media"]["href"].endswith("/media")


@pytest.mark.asyncio
async def test_vocabulary_and_media_links_are_navigable(async_client, auth_headers) -> None:
    vocab_response = await async_client.post(
        "/v1/vocabularies",
        headers=auth_headers,
        json={"name": f"links-{uuid.uuid4().hex}", "is_hierarchical": True},
    )
    assert vocab_response.status_code == 201, vocab_response.text
    vocabulary = vocab_response.json()
    vocab_id = vocabulary["id"]
    assert vocabulary["_links"]["terms"]["href"] == f"/v1/vocabularies/{vocab_id}/terms"
    assert (await async_client.get(vocabulary["_links"]["self"]["href"], headers=auth_headers)).status_code == 200

    term_response = await async_client.post(
        f"/v1/vocabularies/{vocab_id}/terms",
        headers=auth_headers,
        json={"vocabulary_id": vocab_id, "term": "photography", "label": {"en": "Photography"}},
    )
    assert term_response.status_code == 201, term_response.text
    term = term_response.json()
    assert (await async_client.get(term["_links"]["self"]["href"], headers=auth_headers)).status_code == 200

    object_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": f"LINK-MEDIA-{uuid.uuid4().hex}", "status": "draft", "metadata_": {}},
    )
    object_id = object_response.json()["id"]
    from katalon.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        media = MediaFile(
            object_id=uuid.UUID(object_id),
            filename="licensed.jpg",
            mime_type="image/jpeg",
            file_path="/not-needed-for-listing.jpg",
            status="ready",
            license_uri="https://creativecommons.org/licenses/by/4.0/",
        )
        session.add(media)
        await session.commit()

    media_response = await async_client.get(f"/v1/objects/{object_id}/media", headers=auth_headers)
    assert media_response.status_code == 200, media_response.text
    links = media_response.json()[0]["_links"]
    assert links["object"]["href"] == f"/v1/objects/{object_id}"
    assert links["file"]["href"].endswith("/file")
    assert links["license"]["href"] == "https://creativecommons.org/licenses/by/4.0/"

    portal_vocabularies = await async_client.get("/portal/v1/vocabularies")
    assert portal_vocabularies.status_code == 200
    portal_vocab = portal_vocabularies.json()[0]
    assert portal_vocab["_links"]["self"]["href"].startswith("/portal/v1/vocabularies/")
    assert portal_vocab["_links"]["terms"]["href"].endswith("/terms")
    assert (await async_client.get(portal_vocab["_links"]["self"]["href"])).status_code == 200


@pytest.mark.asyncio
async def test_portal_record_media_and_term_links(async_client, auth_headers) -> None:
    object_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": f"LINK-PUB-{uuid.uuid4().hex}", "status": "public", "metadata_": {"label": "Public object"}},
    )
    assert object_response.status_code == 201, object_response.text
    object_id = object_response.json()["id"]

    portal_object = await async_client.get(f"/portal/v1/objects/{object_id}")
    assert portal_object.status_code == 200, portal_object.text
    record_links = portal_object.json()["_links"]
    assert record_links["self"]["href"] == f"/portal/v1/objects/{object_id}"
    assert record_links["relations"]["href"] == f"/portal/v1/relations?from_type=object&from_id={object_id}"
    assert record_links["media"]["href"] == f"/portal/v1/objects/{object_id}/media"

    from katalon.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        media = MediaFile(
            object_id=uuid.UUID(object_id),
            filename="licensed.jpg",
            mime_type="image/jpeg",
            file_path="/not-needed-for-listing.jpg",
            status="ready",
            license_uri="https://creativecommons.org/licenses/by/4.0/",
        )
        session.add(media)
        await session.commit()

    portal_media = await async_client.get(f"/portal/v1/objects/{object_id}/media")
    assert portal_media.status_code == 200, portal_media.text
    media_links = portal_media.json()[0]["_links"]
    assert media_links["object"]["href"] == f"/portal/v1/objects/{object_id}"
    assert media_links["file"]["href"].endswith("/file")
    assert media_links["license"]["href"] == "https://creativecommons.org/licenses/by/4.0/"

    portal_vocabs = await async_client.get("/portal/v1/vocabularies")
    relation_types_id = portal_vocabs.json()[0]["id"]
    portal_terms = await async_client.get(f"/portal/v1/vocabularies/{relation_types_id}/terms")
    assert portal_terms.status_code == 200, portal_terms.text
    terms = portal_terms.json()
    if terms:
        term = terms[0]
        assert term["_links"]["self"]["href"] == (
            f"/portal/v1/vocabularies/{relation_types_id}/terms/{term['id']}"
        )
        assert term["_links"]["vocabulary"]["href"] == f"/portal/v1/vocabularies/{relation_types_id}"
        assert (await async_client.get(term["_links"]["self"]["href"])).status_code == 200
