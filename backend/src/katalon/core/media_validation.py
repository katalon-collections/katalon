from pathlib import Path

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png", "image/tiff", "image/webp"}
PIL_MIME_BY_FORMAT = {
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
