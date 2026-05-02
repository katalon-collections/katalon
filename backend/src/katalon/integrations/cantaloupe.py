import uuid

import httpx

from katalon.config import settings


async def fetch_image_info(filename: str) -> tuple[int | None, int | None]:
    """Fetch info.json from Cantaloupe (internal URL) to get image dimensions.

    Returns (width, height) or (None, None) on failure.
    """
    internal_base = f"{settings.cantaloupe_url}/iiif/3"
    url = f"{internal_base}/{filename}/info.json"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return data.get("width"), data.get("height")
    except Exception:
        return None, None


def build_manifest(
    media_file_id: uuid.UUID,
    filename: str,
    width: int | None = None,
    height: int | None = None,
) -> dict:
    """Build a minimal IIIF Presentation API 3.0 manifest for a media file."""
    public_base = settings.cantaloupe_public_url or settings.cantaloupe_url
    base = f"{public_base}/iiif/3"
    identifier = filename  # e.g. "<uuid>.jpg" — matches the file on disk

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
        canvas["body"] = canvas["items"][0]["items"][0]["body"]
    if height is not None:
        canvas["height"] = height

    return {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "id": f"{base}/{identifier}/manifest",
        "type": "Manifest",
        "items": [canvas],
    }
