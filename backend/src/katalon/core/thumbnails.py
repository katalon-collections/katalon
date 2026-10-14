# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""IIIF derivative sizes for portal thumbnails, shared by the thumbnail route,
the warm-up task and (mirrored, see frontend/portal/src/utils/thumbnails.ts)
the portal. Heights, because the portal grid has a fixed row height."""

from __future__ import annotations

THUMBNAIL_HEIGHT = 300
# Second size for high-density screens (srcset 2x); warmed alongside the base size.
THUMBNAIL_HEIGHT_HIDPI = 600
THUMBNAIL_HEIGHTS = (THUMBNAIL_HEIGHT, THUMBNAIL_HEIGHT_HIDPI)


def thumbnail_path(identifier: str, height: int = THUMBNAIL_HEIGHT) -> str:
    """Host-relative IIIF Image API path of a thumbnail derivative."""
    return f"/iiif/3/{identifier}/full/,{height}/0/default.jpg"
