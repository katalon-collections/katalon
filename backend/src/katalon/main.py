from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from katalon.api.v1 import auth, audit, entities, media, objects, occurrences, places, relations, schema_admin, search, theme, vocabularies
from katalon.config import settings

app = FastAPI(
    title="Katalon API",
    description="Metadata Management System for GLAM collections",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/v1")
app.include_router(objects.router, prefix="/v1")
app.include_router(schema_admin.router, prefix="/v1")
app.include_router(vocabularies.router, prefix="/v1")
app.include_router(audit.router, prefix="/v1")
app.include_router(entities.router, prefix="/v1")
app.include_router(places.router, prefix="/v1")
app.include_router(occurrences.router, prefix="/v1")
app.include_router(relations.router, prefix="/v1")
app.include_router(media.router, prefix="/v1")
app.include_router(theme.router, prefix="/v1")
app.include_router(search.router, prefix="/v1")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
