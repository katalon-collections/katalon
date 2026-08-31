from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select

from katalon.core.models import FieldDefinition
from katalon.integrations.elasticsearch import search_ids_by_filter
from katalon.services.search_service import date_bounds

PUBLIC_TYPES = ("object", "entity", "place", "occurrence")
MAX_RELATION_DEPTH = 2
INTERMEDIATE_RESULT_LIMIT = 10000


class AdvancedFieldClause(BaseModel):
    kind: Literal["field"] = "field"
    field: str
    operator: str
    value: Any = None


class AdvancedRelationClause(BaseModel):
    kind: Literal["relation"] = "relation"
    field: str
    group: AdvancedGroup


AdvancedClause = Annotated[
    AdvancedFieldClause | AdvancedRelationClause,
    Field(discriminator="kind"),
]


class AdvancedGroup(BaseModel):
    mode: Literal["all", "any"] = "all"
    clauses: list[AdvancedClause] = Field(min_length=1, max_length=20)


class AdvancedQuery(BaseModel):
    version: Literal[1] = 1
    record_type: Literal["object", "entity", "place", "occurrence"]
    group: AdvancedGroup


AdvancedRelationClause.model_rebuild()
AdvancedGroup.model_rebuild()


async def _fields_for_type(db: Any, record_type: str) -> dict[str, FieldDefinition]:
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.target_type == record_type,
            FieldDefinition.is_deleted.is_(False),
            FieldDefinition.is_public.is_(True),
            FieldDefinition.is_searchable.is_(True),
            FieldDefinition.parent_id.is_(None),
        )
    )
    return {field.name: field for field in result.scalars().all()}


def _nested_field(name: str, value_query: dict[str, Any] | None = None) -> dict[str, Any]:
    filters: list[dict[str, Any]] = [{"term": {"adv_fields.name": name}}]
    if value_query:
        filters.append(value_query)
    return {
        "nested": {
            "path": "adv_fields",
            "query": {"bool": {"filter": filters}},
        }
    }


def _negate(query: dict[str, Any]) -> dict[str, Any]:
    return {"bool": {"must_not": [query]}}


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Zahlenwert ist ungültig.") from exc


def _pair(value: Any) -> tuple[Any, Any]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Der Operator 'zwischen' benötigt zwei Werte.")
    return value[0], value[1]


def _open_bound(path: str, *, lte: int | None = None, gte: int | None = None) -> dict[str, Any]:
    range_value = {key: value for key, value in {"lte": lte, "gte": gte}.items() if value is not None}
    return {
        "bool": {
            "should": [
                {"range": {path: range_value}},
                {"bool": {"must_not": [{"exists": {"field": path}}]}},
            ],
            "minimum_should_match": 1,
        }
    }


def _date_overlap(name: str, lower: int | None, upper: int | None) -> dict[str, Any]:
    filters: list[dict[str, Any]] = [{"term": {"adv_fields.name": name}}]
    if upper is not None:
        filters.append(_open_bound("adv_fields.date_min", lte=upper))
    if lower is not None:
        filters.append(_open_bound("adv_fields.date_max", gte=lower))
    return {"nested": {"path": "adv_fields", "query": {"bool": {"filter": filters}}}}


def _field_filter(field: FieldDefinition, clause: AdvancedFieldClause) -> dict[str, Any]:
    operator = clause.operator
    if operator in {"exists", "not_exists"}:
        query = _nested_field(field.name)
        return _negate(query) if operator == "not_exists" else query

    field_type = field.field_type
    if field_type in {"text", "richtext"}:
        if operator not in {"contains", "not_contains", "eq", "neq"}:
            raise ValueError(f"Operator '{operator}' passt nicht zu Textfeldern.")
        if not isinstance(clause.value, str) or not clause.value.strip():
            raise ValueError("Textwert darf nicht leer sein.")
        path = "adv_fields.keyword_value"
        if operator in {"contains", "not_contains"}:
            escaped = clause.value.replace("\\", "\\\\").replace("*", "\\*").replace("?", "\\?")
            value_query: dict[str, Any] = {
                "wildcard": {path: {"value": f"*{escaped}*", "case_insensitive": True}}
            }
        else:
            value_query = {"term": {path: clause.value}}
        query = _nested_field(field.name, value_query)
        return _negate(query) if operator in {"not_contains", "neq"} else query

    if field_type in {"vocab", "vocab_free", "authority", "pid", "url"}:
        if operator not in {"eq", "neq"}:
            raise ValueError(f"Operator '{operator}' passt nicht zu Auswahlfeldern.")
        if not isinstance(clause.value, str) or not clause.value.strip():
            raise ValueError("Auswahlwert darf nicht leer sein.")
        query = _nested_field(field.name, {"term": {"adv_fields.keyword_value": clause.value}})
        return _negate(query) if operator == "neq" else query

    if field_type == "boolean":
        if operator not in {"eq", "neq"} or not isinstance(clause.value, bool):
            raise ValueError("Boolean-Felder erwarten 'ist ja' oder 'ist nein'.")
        query = _nested_field(field.name, {"term": {"adv_fields.bool_value": clause.value}})
        return _negate(query) if operator == "neq" else query

    if field_type == "number":
        if operator == "between":
            start, end = _pair(clause.value)
            numeric_lower, numeric_upper = _number(start), _number(end)
            if numeric_lower > numeric_upper:
                raise ValueError("Die untere Zahlengrenze muss vor der oberen liegen.")
            value_query = {"range": {"adv_fields.number_value": {"gte": numeric_lower, "lte": numeric_upper}}}
        elif operator in {"eq", "neq"}:
            value_query = {"term": {"adv_fields.number_value": _number(clause.value)}}
        elif operator in {"lt", "lte", "gt", "gte"}:
            value_query = {"range": {"adv_fields.number_value": {operator: _number(clause.value)}}}
        else:
            raise ValueError(f"Operator '{operator}' passt nicht zu Zahlenfeldern.")
        query = _nested_field(field.name, value_query)
        return _negate(query) if operator == "neq" else query

    if field_type == "date":
        if operator == "between":
            start, end = _pair(clause.value)
            date_lower = date_bounds(str(start))[0]
            date_upper = date_bounds(str(end))[1]
            if date_lower is not None and date_upper is not None and date_lower > date_upper:
                raise ValueError("Die untere Datumsgrenze muss vor der oberen liegen.")
            return _date_overlap(field.name, date_lower, date_upper)
        date_lower, date_upper = date_bounds(str(clause.value))
        if operator == "before":
            if date_lower is None:
                raise ValueError("'Vor' benötigt eine geschlossene Datumsgrenze.")
            return _nested_field(field.name, {"range": {"adv_fields.date_max": {"lt": date_lower}}})
        if operator == "after":
            if date_upper is None:
                raise ValueError("'Nach' benötigt eine geschlossene Datumsgrenze.")
            return _nested_field(field.name, {"range": {"adv_fields.date_min": {"gt": date_upper}}})
        if operator == "on":
            return _date_overlap(field.name, date_lower, date_upper)
        raise ValueError(f"Operator '{operator}' passt nicht zu Datumsfeldern.")

    raise ValueError(f"Feldtyp '{field_type}' wird in der erweiterten Suche nicht unterstützt.")


def _group_filter(mode: str, clauses: list[dict[str, Any]]) -> dict[str, Any]:
    if mode == "any":
        return {"bool": {"should": clauses, "minimum_should_match": 1}}
    return {"bool": {"filter": clauses}}


async def _resolve_group(
    db: Any,
    record_type: str,
    group: AdvancedGroup,
    relation_depth: int,
) -> dict[str, Any]:
    fields = await _fields_for_type(db, record_type)
    resolved: list[dict[str, Any]] = []
    for clause in group.clauses:
        field = fields.get(clause.field)
        if field is None:
            raise ValueError(f"Öffentliches Suchfeld '{clause.field}' existiert für {record_type} nicht.")
        if isinstance(clause, AdvancedFieldClause):
            if field.field_type == "relation":
                raise ValueError(f"Relationsfeld '{field.name}' benötigt eine Zielbedingung.")
            resolved.append(_field_filter(field, clause))
            continue
        if field.field_type != "relation":
            raise ValueError(f"Feld '{field.name}' ist kein Relationsfeld.")
        if relation_depth >= MAX_RELATION_DEPTH:
            raise ValueError("Die erweiterte Suche erlaubt höchstens zwei Relationsschritte.")
        target_type = str((field.settings or {}).get("target_type", ""))
        if target_type not in PUBLIC_TYPES:
            raise ValueError(f"Relationsfeld '{field.name}' hat keinen öffentlichen Zieltyp.")
        target_filter = await _resolve_group(db, target_type, clause.group, relation_depth + 1)
        target_ids, truncated = await search_ids_by_filter(
            target_type, target_filter, limit=INTERMEDIATE_RESULT_LIMIT
        )
        if truncated:
            raise ValueError("Zwischenergebnis zu groß. Bitte die Relationsbedingung weiter einschränken.")
        if not target_ids:
            resolved.append({"match_none": {}})
            continue
        filters: list[dict[str, Any]] = [
            {"term": {"adv_relations.source_field": field.name}},
            {"terms": {"adv_relations.target_id": target_ids}},
        ]
        fixed_type = (field.settings or {}).get("fixed_relation_type")
        if fixed_type:
            filters.append({"term": {"adv_relations.relation_type": fixed_type}})
        resolved.append({
            "nested": {
                "path": "adv_relations",
                "query": {"bool": {"filter": filters}},
            }
        })
    return _group_filter(group.mode, resolved)


async def resolve_query(db: Any, query: AdvancedQuery) -> dict[str, Any]:
    return await _resolve_group(db, query.record_type, query.group, 0)
