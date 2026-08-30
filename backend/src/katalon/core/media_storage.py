import re
import unicodedata
import uuid
from pathlib import Path
from urllib.parse import quote

from katalon.config import settings


def safe_filename(filename: str) -> str:
    """Return a portable filename while retaining a recognizable original name."""
    name = Path(filename).name
    suffix = Path(name).suffix.lower()
    stem = Path(name).stem
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip(".-") or "upload"
    return f"{stem[:180]}{suffix[:20]}"


def storage_key(media_id: uuid.UUID, filename: str) -> str:
    """Build the relative, sharded storage key for a managed media file."""
    return f"{media_id.hex[:2]}/{media_id}--{safe_filename(filename)}"


def storage_path(key: str) -> Path:
    """Resolve a media key under MEDIA_ROOT without allowing path traversal."""
    root = Path(settings.media_root).resolve()
    path = (root / key).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Ungültiger Media-Storage-Key")
    return path


def relative_storage_key(value: str, media_root: str | Path | None = None) -> str:
    """Convert a legacy absolute path below MEDIA_ROOT to its relative storage key."""
    path = Path(value)
    if not path.is_absolute():
        return value
    root = Path(media_root or settings.media_root).resolve()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"Medienpfad liegt nicht unter MEDIA_ROOT: {value}") from exc


def pyramid_storage_key(key: str) -> str:
    path = Path(key)
    return str(path.with_name(f"{path.stem}_pyramid.tif"))


def iiif_identifier(key: str | None, fallback_key: str) -> str:
    """Use an encoded relative key so Cantaloupe receives it as one identifier."""
    return quote(key or fallback_key, safe="")
