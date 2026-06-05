from pathlib import Path

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png", "image/tiff", "image/webp"}
PIL_MIME_BY_FORMAT = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "TIFF": "image/tiff",
    "WEBP": "image/webp",
}

Image.MAX_IMAGE_PIXELS = 120_000_000


def verified_image_mime(path: Path) -> str:
    try:
        with Image.open(path) as image:
            image.verify()
            mime_type = PIL_MIME_BY_FORMAT.get(image.format or "")
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=415, detail="Datei ist kein gültiges Bild") from exc
    if mime_type not in ALLOWED_IMAGE_MIME:
        raise HTTPException(status_code=415, detail="Nicht unterstützter Bildtyp")
    return mime_type
