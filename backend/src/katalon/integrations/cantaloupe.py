import uuid

import httpx

from katalon.config import settings


def build_manifest(media_file_id: uuid.UUID) -> dict:
    """Build a minimal IIIF Presentation API 3.0 manifest for a media file."""
    base = f"{settings.cantaloupe_url}/iiif/3"
    identifier = str(media_file_id)

    return {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "id": f"{base}/{identifier}/manifest",
        "type": "Manifest",
        "items": [
            {
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
        ],
    }
