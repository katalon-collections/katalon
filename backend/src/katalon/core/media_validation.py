# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from pathlib import Path

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png", "image/tiff", "image/webp"}
PIL_MIME_BY_FORMAT = {
    "GIF": "image/gif",
    "JPEG": "image/jpeg",
    "MPO": "image/jpeg",
    "PNG": "image/png",
    "TIFF": "image/tiff",
    "WEBP": "image/webp",
}

ALLOWED_PDF_MIME = {"application/pdf"}
ALLOWED_AUDIO_MIME = {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/ogg"}
ALLOWED_VIDEO_MIME = {"video/mp4", "video/webm"}
ALLOWED_MODEL_MIME = {"model/gltf-binary", "model/gltf+json"}

ALLOWED_MEDIA_MIME = (
    ALLOWED_IMAGE_MIME | ALLOWED_PDF_MIME | ALLOWED_AUDIO_MIME | ALLOWED_VIDEO_MIME | ALLOWED_MODEL_MIME
)

ALLOWED_PAGE_ASSET_IMAGE_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_PAGE_ASSET_DOC_MIME = {"application/pdf"}
ALLOWED_PAGE_ASSET_VIDEO_MIME = {"video/mp4"}
ALLOWED_PAGE_ASSET_MIME = (
    ALLOWED_PAGE_ASSET_IMAGE_MIME | ALLOWED_PAGE_ASSET_DOC_MIME | ALLOWED_PAGE_ASSET_VIDEO_MIME
)

PAGE_ASSET_EXTENSION_FALLBACK = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".pdf": "application/pdf",
    ".mp4": "video/mp4",
}

Image.MAX_IMAGE_PIXELS = 120_000_000


EXTENSION_MIME_FALLBACK = {
    ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json",
}


def resolve_upload_mime(content_type: str | None, filename: str) -> str | None:
    """Browsers often send no/wrong Content-Type for less common formats like .glb."""
    if content_type in ALLOWED_MEDIA_MIME:
        return content_type
    suffix = Path(filename).suffix.lower()
    return EXTENSION_MIME_FALLBACK.get(suffix)


def media_category(mime_type: str) -> str:
    if mime_type in ALLOWED_IMAGE_MIME:
        return "image"
    if mime_type in ALLOWED_PDF_MIME:
        return "pdf"
    if mime_type in ALLOWED_AUDIO_MIME:
        return "audio"
    if mime_type in ALLOWED_VIDEO_MIME:
        return "video"
    if mime_type in ALLOWED_MODEL_MIME:
        return "model"
    return "other"


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


def resolve_page_asset_mime(content_type: str | None, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".svg" or content_type == "image/svg+xml":
        raise HTTPException(
            status_code=415,
            detail="SVG-Dateien sind aus Sicherheitsgründen nicht als Seiten-Assets erlaubt.",
        )
    if content_type in ALLOWED_PAGE_ASSET_MIME:
        return content_type
    fallback = PAGE_ASSET_EXTENSION_FALLBACK.get(suffix)
    if fallback:
        return fallback
    raise HTTPException(
        status_code=415,
        detail="Dateityp nicht unterstützt. Erlaubt sind JPG, PNG, WebP, GIF, PDF und MP4.",
    )


def verify_page_asset(path: Path, mime_type: str) -> str:
    """Validate content format matches expected mime_type."""
    if mime_type in ALLOWED_PAGE_ASSET_IMAGE_MIME:
        try:
            with Image.open(path) as image:
                image.verify()
                actual_mime = PIL_MIME_BY_FORMAT.get(image.format or "")
        except (UnidentifiedImageError, OSError) as exc:
            raise HTTPException(status_code=415, detail="Datei ist kein gültiges Bild") from exc
        if actual_mime not in ALLOWED_PAGE_ASSET_IMAGE_MIME:
            raise HTTPException(status_code=415, detail="Nicht unterstützter Bildtyp")
        return actual_mime

    if mime_type in ALLOWED_PAGE_ASSET_DOC_MIME:
        with path.open("rb") as f:
            header = f.read(5)
        if header != b"%PDF-":
            raise HTTPException(status_code=415, detail="Datei ist keine gültige PDF-Datei")
        return mime_type

    if mime_type in ALLOWED_PAGE_ASSET_VIDEO_MIME:
        with path.open("rb") as f:
            box = f.read(12)
        if len(box) < 8 or b"ftyp" not in box:
            raise HTTPException(status_code=415, detail="Datei ist kein gültiges MP4-Video")
        return mime_type

    raise HTTPException(status_code=415, detail="Nicht unterstützter Medientyp")

