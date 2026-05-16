import uuid
from pathlib import Path

import httpx

from katalon.config import settings


def _public_base() -> str:
    return settings.cantaloupe_public_url or settings.cantaloupe_url


class CantaloupeError(Exception):
    """Permanent error from Cantaloupe (e.g. unreadable image). Should not be retried."""


async def fetch_image_info(filename: str) -> tuple[int | None, int | None]:
    """Fetch info.json from Cantaloupe to get image dimensions and trigger lazy processing.

    Raises CantaloupeError on HTTP 4xx (permanent). Returns (None, None) on transient errors.
    """
    url = f"{settings.cantaloupe_url}/iiif/3/{filename}/info.json"
    timeout = settings.cantaloupe_task_timeout
    try:
        async with httpx.AsyncClient(timeout=float(timeout)) as client:
            resp = await client.get(url)
            if resp.status_code >= 400 and resp.status_code < 500:
                raise CantaloupeError(f"Cantaloupe returned {resp.status_code} for {filename}")
            resp.raise_for_status()
            data = resp.json()
            return data.get("width"), data.get("height")
    except CantaloupeError:
        raise
    except Exception:
        return None, None


def _build_canvas(manifest_base: str, index: int, filename: str, stored_manifest: dict | None) -> dict:
    """Build a single IIIF Canvas for one media file."""
    img_base = f"{_public_base()}/iiif/3/{filename}"
    canvas_id = f"{manifest_base}/canvas/{index}"

    width = height = None
    if stored_manifest and stored_manifest.get("items"):
        c = stored_manifest["items"][0]
        width = c.get("width")
        height = c.get("height")

    canvas: dict = {
        "id": canvas_id,
        "type": "Canvas",
        "items": [
            {
                "id": f"{canvas_id}/annotation-page",
                "type": "AnnotationPage",
                "items": [
                    {
                        "id": f"{canvas_id}/annotation",
                        "type": "Annotation",
                        "motivation": "painting",
                        "body": {
                            "id": f"{img_base}/full/max/0/default.jpg",
                            "type": "Image",
                            "service": [
                                {
                                    "id": img_base,
                                    "type": "ImageService3",
                                    "profile": "level2",
                                }
                            ],
                        },
                        "target": canvas_id,
                    }
                ],
            }
        ],
    }
    if width is not None:
        canvas["width"] = width
    if height is not None:
        canvas["height"] = height
    return canvas


def build_object_manifest(
    manifest_id: str,
    media_items: list[tuple[str, dict | None]],
    obj: object | None = None,
    field_defs: list | None = None,
    homepage_url: str | None = None,
) -> dict:
    """Build a multi-canvas IIIF Presentation 3.0 manifest for an object."""
    canvases = [
        _build_canvas(manifest_id, i, filename, stored)
        for i, (filename, stored) in enumerate(media_items, 1)
    ]

    manifest: dict = {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "id": manifest_id,
        "type": "Manifest",
        "items": canvases,
    }

    if obj is not None:
        meta = obj.metadata_ if isinstance(obj.metadata_, dict) else {}  # type: ignore[union-attr]

        # label — required by IIIF spec
        raw_title = meta.get("title") or meta.get("name") or getattr(obj, "idno", None) or str(getattr(obj, "id", ""))
        title_str = raw_title[0].get("value", str(raw_title)) if isinstance(raw_title, list) and raw_title else str(raw_title)
        manifest["label"] = {"none": [title_str]}

        # summary from description field
        raw_desc = meta.get("description")
        if raw_desc:
            desc_str = raw_desc[0].get("value", str(raw_desc)) if isinstance(raw_desc, list) and raw_desc else str(raw_desc)
            manifest["summary"] = {"none": [desc_str]}

        # metadata array from field_definitions
        if field_defs:
            metadata_entries = []
            for fd in field_defs:
                raw = meta.get(fd.name)
                if not raw:
                    continue
                values = [v.get("value", str(v)) if isinstance(v, dict) else str(v) for v in (raw if isinstance(raw, list) else [raw])]
                values = [v for v in values if v]
                if not values:
                    continue
                label_dict = fd.label if isinstance(fd.label, dict) else {}
                label = {lang: [lbl] for lang, lbl in label_dict.items()} or {"none": [fd.name]}
                metadata_entries.append({"label": label, "value": {"none": values}})
            if metadata_entries:
                manifest["metadata"] = metadata_entries

        # homepage link back to portal
        if homepage_url:
            manifest["homepage"] = [{"id": homepage_url, "type": "Text", "format": "text/html"}]

        # requiredStatement with idno
        idno = getattr(obj, "idno", None)
        if idno:
            manifest["requiredStatement"] = {
                "label": {"de": ["Inventar-Nr."], "en": ["Inventory No."]},
                "value": {"none": [idno]},
            }

    return manifest


def build_manifest(
    media_file_id: uuid.UUID,
    filename: str,
    width: int | None = None,
    height: int | None = None,
) -> dict:
    """Build a single-canvas IIIF manifest for one media file (stored per-file in DB)."""
    base = f"{_public_base()}/iiif/3"
    identifier = filename
    canvas: dict = {
        "id": f"{base}/{identifier}/canvas/1",
        "type": "Canvas",
        "items": [
            {
                "id": f"{base}/{identifier}/annotation-page/1",
                "type": "AnnotationPage",
                "items": [
                    {
                        "id": f"{base}/{identifier}/annotation/1",
                        "type": "Annotation",
                        "motivation": "painting",
                        "body": {
                            "id": f"{base}/{identifier}/full/max/0/default.jpg",
                            "type": "Image",
                            "service": [
                                {
                                    "id": f"{base}/{identifier}",
                                    "type": "ImageService3",
                                    "profile": "level2",
                                }
                            ],
                        },
                        "target": f"{base}/{identifier}/canvas/1",
                    }
                ],
            }
        ],
    }
    if width is not None:
        canvas["width"] = width
    if height is not None:
        canvas["height"] = height
    return {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "id": f"{base}/{identifier}/manifest",
        "type": "Manifest",
        "items": [canvas],
    }
