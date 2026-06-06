from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from katalon.core.dependencies import DBDep, require_role
from katalon.core.models import Entity, Object, Occurrence, Place
from katalon.integrations.elasticsearch import count_by_type

router = APIRouter(prefix="/admin/index-health", tags=["admin"])

_MODEL_MAP: dict = {
    "object": Object, "entity": Entity, "place": Place, "occurrence": Occurrence,
}


class TypeHealth(BaseModel):
    db: int
    es: int
    delta: int


class IndexHealthResponse(BaseModel):
    types: dict[str, TypeHealth]


@router.get("", response_model=IndexHealthResponse, dependencies=[require_role("admin")])
async def get_index_health(db: DBDep) -> IndexHealthResponse:
    types: dict[str, TypeHealth] = {}
    for record_type, model in _MODEL_MAP.items():
        db_count = (await db.execute(select(func.count()).select_from(model))).scalar_one()
        es_count = await count_by_type(record_type)
        types[record_type] = TypeHealth(db=db_count, es=es_count, delta=db_count - es_count)
    return IndexHealthResponse(types=types)


@router.post("/reconcile", dependencies=[require_role("admin")])
async def trigger_reconciliation(mode: str = "id_diff") -> dict[str, str]:
    if mode not in ("count", "id_diff"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="mode must be 'count' or 'id_diff'")

    from katalon.workers.index_tasks import reconciliation_job_task
    reconciliation_job_task.delay(mode=mode, force=True)
    return {"status": "started", "mode": mode}
