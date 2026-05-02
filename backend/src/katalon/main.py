from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select

from katalon.api.v1 import (
    auth, audit, authority, entities, importer, media, objects,
    occurrences, oai, places, relations, schema_admin, search, theme, users, vocabularies,
)
from katalon.api.v1.auth import hash_password
from katalon.config import settings
from katalon.core.models import User, Vocabulary, VocabularyTerm
from katalon.database import AsyncSessionLocal

async def _ensure_admin() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none() is None:
            admin = User(
                email=settings.default_admin_email,
                hashed_password=hash_password(settings.default_admin_password),
                role="admin",
            )
            db.add(admin)
            await db.commit()


_DEFAULT_MEDIA_TYPES = [
    ("vorderseite", {"de": "Vorderseite", "en": "Front"}),
    ("rueckseite",  {"de": "Rückseite",   "en": "Back"}),
    ("detail",      {"de": "Detail",      "en": "Detail"}),
    ("uebersicht",  {"de": "Übersicht",   "en": "Overview"}),
    ("innen",       {"de": "Innen",       "en": "Interior"}),
    ("signatur",    {"de": "Signatur",    "en": "Signature"}),
]


async def _ensure_media_types_vocab() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Vocabulary).where(Vocabulary.name == "media_types"))
        vocab = result.scalar_one_or_none()
        if vocab is None:
            vocab = Vocabulary(name="media_types", is_hierarchical=False)
            db.add(vocab)
            await db.flush()
            for term_key, label in _DEFAULT_MEDIA_TYPES:
                db.add(VocabularyTerm(vocabulary_id=vocab.id, term=term_key, label=label))
            await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _ensure_admin()
    await _ensure_media_types_vocab()
    yield


limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(
    lifespan=lifespan,
    title="Katalon API",
    description="Metadata Management System for GLAM collections",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/v1")
app.include_router(users.router, prefix="/v1")
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
app.include_router(authority.router, prefix="/v1")
app.include_router(importer.router, prefix="/v1")
app.include_router(oai.router, prefix="/v1")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
