# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import asyncio
import uuid
from typing import Any, cast

from katalon.workers.celery_app import celery_app
from katalon.workers.email_tasks import send_user_email
from katalon.workers.enqueue import enqueue, run_after_commit_hooks


def _queue_import_notification(
    user_id: str | None, record_type: str, result: dict[str, Any]
) -> None:
    if not user_id:
        return
    if "error" in result:
        subject = "Katalon: Import fehlgeschlagen"
        text = f"Der Import von {record_type}-Datensätzen konnte nicht ausgeführt werden."
    else:
        subject = "Katalon: Import abgeschlossen"
        text = (
            f"Der Import von {record_type}-Datensätzen ist abgeschlossen.\n\n"
            f"Neu: {result['created']}\nAktualisiert: {result['updated']}\n"
            f"Übersprungen: {result['skipped']}\nFehlerhafte Zeilen: {len(result['errors'])}"
        )
    enqueue(send_user_email, user_id, subject, text)


@celery_app.task(name="katalon.import_records", bind=True)
def import_records_task(
    self: Any,
    record_type: str,
    rows: list[dict[str, str]],
    mapping: dict[str, str] | dict[str, Any],
    idno_strategy: str = "auto",  # "auto" | "column" | "skip"
    upsert_strategy: str = "skip",  # "skip" | "merge" | "replace"
    auto_publish: bool = False,
    user_id: str | None = None,
    subtype: str | None = None,
    fields_to_create: list[dict[str, Any]] | None = None,
    media_selector: str | None = None,
) -> dict[str, Any]:
    """Import records from CSV/Excel with validation, audit logging, and ES indexing.

    Args:
        record_type: object | entity | place | occurrence
        rows: list of CSV row dicts
        mapping: {csv_column -> field_name} or {csv_column -> {"target": field_name, "delimiter": "..."}}
        idno_strategy: how to handle idno — "auto" generates one, "column" reads from
                       mapped "idno" column, "skip" leaves it null
        upsert_strategy: how to handle existing records by idno — "skip" ignores duplicates,
                         "merge" adds mapped fields only, "replace" replaces mapped values
                         while retaining unmapped legacy metadata
        auto_publish: if True, attempt to publish each record after creation
        user_id: UUID of the user who triggered the import
    """
    from fastapi import HTTPException
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.orm.exc import StaleDataError
    from sqlalchemy.pool import NullPool

    from katalon.config import settings
    from katalon.core.dependencies import has_feature_permission, has_record_permission
    from katalon.core.models import (
        AdminConfig,
        Entity,
        FieldDefinition,
        MediaImportReference,
        Object,
        Occurrence,
        Place,
        User,
        Vocabulary,
        VocabularyTerm,
    )
    from katalon.services.audit_service import diff_fields, log_change
    from katalon.services.idno_service import consume_next_idno
    from katalon.services.importer_service import apply_mapping
    from katalon.services.lock_service import enforce_not_locked
    from katalon.services.media_batch_import_service import media_references_for_rows
    from katalon.services.presence_service import enforce_not_blocked
    from katalon.services.publish_service import publish_record
    from katalon.services.relation_service import sync_schema_relations
    from katalon.services.schema_service import prepare_metadata, validate_metadata
    from katalon.services.search_service import index_record
    from katalon.services.subtype_service import ensure_subtype_exists

    # NullPool avoids binding connections to a previous event loop across Celery task invocations
    _engine = create_async_engine(settings.database_url, poolclass=NullPool)
    AsyncSessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    model_map: dict[str, type[Object] | type[Entity] | type[Place] | type[Occurrence]] = {
        "object": Object,
        "entity": Entity,
        "place": Place,
        "occurrence": Occurrence,
    }
    model = model_map.get(record_type)
    if model is None:
        result = {"error": f"Unknown record_type: {record_type}"}
        _queue_import_notification(user_id, record_type, result)
        return result
    if media_selector and record_type != "object":
        result = {"error": "Media references are only supported for objects"}
        _queue_import_notification(user_id, record_type, result)
        return result

    media_references, media_stats = (
        media_references_for_rows(cast(list[dict[str, object]], rows), media_selector)
        if media_selector
        else ([[] for _ in rows], {"conflicts": []})
    )
    if media_selector and not media_stats["selector_found"]:
        result = {"error": f"Media selector not found: {media_selector}"}
        _queue_import_notification(user_id, record_type, result)
        return result
    if media_stats["conflicts"]:
        result = {"error": "A media filename is assigned to multiple records"}
        _queue_import_notification(user_id, record_type, result)
        return result

    # Subtype field name varies by type
    subtype_field = {
        "object": "object_type",
        "entity": "entity_type",
        "place": "place_type",
        "occurrence": "occurrence_type",
    }.get(record_type)

    # Check if idno is mapped via __idno__
    _mapping_targets = []
    for v in mapping.values():
        if isinstance(v, dict):
            _mapping_targets.append(v.get("target", ""))
        else:
            _mapping_targets.append(v)
    has_idno_column = "__idno__" in _mapping_targets

    import redis as redis_lib

    from katalon.config import settings as _settings

    _redis = redis_lib.from_url(_settings.redis_url, decode_responses=True)  # type: ignore[no-untyped-call]  # redis stubs untyped

    def _is_cancelled() -> bool:
        return bool(_redis.get(f"cancel:{self.request.id}"))

    created = 0
    updated = 0
    skipped = 0
    published = 0
    publish_failed = 0
    index_failed = 0
    media_references_created = 0
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    publish_fail_reasons: list[str] = []  # first few unique reasons

    async def _resolve_vocab_terms(
        session: AsyncSession,
        field_defs: dict[str, Any],
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Replace plain string values in vocab fields with {id, label} dicts.

        Looks up existing terms case-insensitively, creates missing ones, and
        caches per-vocabulary to avoid redundant DB queries.
        """
        # Find all vocab fields that have a vocabulary_id configured
        vocab_fields: dict[str, uuid.UUID] = {}
        for fname, fd in field_defs.items():
            if fd.field_type == "vocab":
                vid = (fd.settings or {}).get("vocabulary_id")
                if vid:
                    try:
                        vocab_fields[fname] = uuid.UUID(str(vid))
                    except ValueError:
                        pass

        if not vocab_fields:
            return records

        # Per-vocabulary term cache: vocab_id -> {lower_term -> {id, label}}
        term_cache: dict[uuid.UUID, dict[str, dict[str, Any]]] = {}

        async def get_term(vocab_id: uuid.UUID, term_str: str) -> dict[str, Any] | None:
            if vocab_id not in term_cache:
                res = await session.execute(
                    select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == vocab_id)
                )
                term_cache[vocab_id] = {
                    t.term.strip().lower(): {"id": str(t.id), "label": t.term}
                    for t in res.scalars().all()
                }
            key = term_str.strip().lower()
            if key in term_cache[vocab_id]:
                return term_cache[vocab_id][key]
            # Term does not exist — check the vocabulary exists before creating
            vocab_res = await session.execute(select(Vocabulary).where(Vocabulary.id == vocab_id))
            if vocab_res.scalar_one_or_none() is None:
                return None
            new_term = VocabularyTerm(
                vocabulary_id=vocab_id,
                term=term_str.strip(),
                label={"de": term_str.strip()},
            )
            session.add(new_term)
            await session.flush()
            entry = {"id": str(new_term.id), "label": new_term.term}
            term_cache[vocab_id][key] = entry
            return entry

        for record in records:
            for fname, vocab_id in vocab_fields.items():
                val = record.get(fname)
                if val is None:
                    continue
                if isinstance(val, list):
                    resolved = []
                    for item in val:
                        if isinstance(item, str) and item.strip():
                            entry = await get_term(vocab_id, item)
                            if entry:
                                resolved.append(entry)
                    if resolved:
                        record[fname] = resolved
                    else:
                        record.pop(fname, None)
                elif isinstance(val, str) and val.strip():
                    entry = await get_term(vocab_id, val)
                    if entry:
                        record[fname] = entry
                    else:
                        record.pop(fname, None)

        return records

    async def _import() -> dict[str, Any]:
        nonlocal created, updated, skipped, published, publish_failed, index_failed
        nonlocal media_references_created, publish_fail_reasons

        async with AsyncSessionLocal() as session:
            try:
                user_uuid = uuid.UUID(user_id) if user_id else None
            except ValueError:
                user_uuid = None
            user = await session.get(User, user_uuid) if user_uuid is not None else None
            denial: str | None = None
            if user is None or not user.is_active:
                denial = "Benutzer nicht gefunden oder deaktiviert."
            elif not await has_feature_permission(session, user, "import"):
                denial = "Import-Feature wurde entzogen."
            elif not (
                await has_record_permission(session, user, record_type, "create")
                and await has_record_permission(session, user, record_type, "update")
            ):
                denial = "Schreibrecht für diesen Datensatztyp wurde entzogen."
            if denial:
                self.update_state(
                    state="FAILURE", meta={"current": 0, "total": 0, "stage": "denied"}
                )
                return {
                    "created": 0,
                    "updated": 0,
                    "skipped": 0,
                    "published": 0,
                    "publish_failed": 0,
                    "publish_fail_reasons": [],
                    "index_failed": 0,
                    "media_references_created": 0,
                    "errors": [{"row": None, "error": f"Import-Job abgebrochen: {denial}"}],
                    "warnings": [],
                }
            can_edit_locked = user.role in {"admin", "superuser"}

            # Validate subtype before processing any rows
            await ensure_subtype_exists(session, record_type, subtype)

            # Create field definitions requested alongside this import
            if fields_to_create:
                for f in fields_to_create:
                    name = (f.get("name") or "").strip()
                    if not name:
                        continue
                    existing_fd = (
                        await session.execute(
                            select(FieldDefinition).where(
                                FieldDefinition.target_type == record_type,
                                FieldDefinition.name == name,
                            )
                        )
                    ).scalar_one_or_none()
                    if existing_fd:
                        if existing_fd.is_deleted:
                            existing_fd.is_deleted = False
                            existing_fd.field_type = f.get("field_type", "text")
                            existing_fd.is_repeatable = bool(f.get("is_repeatable", False))
                        continue
                    label: dict[str, str] = {}
                    if f.get("label_de"):
                        label["de"] = f["label_de"].strip()
                    if f.get("label_en"):
                        label["en"] = f["label_en"].strip()
                    session.add(
                        FieldDefinition(
                            target_type=record_type,
                            name=name,
                            label=label,
                            field_type=f.get("field_type", "text"),
                            is_required=False,
                            is_repeatable=bool(f.get("is_repeatable", False)),
                            sort_order=0,
                        )
                    )
                await session.flush()

            # Load field_defs once for type conversion in apply_mapping
            fd_result = await session.execute(
                select(FieldDefinition).where(
                    FieldDefinition.target_type == record_type,
                    FieldDefinition.is_deleted.is_(False),
                )
            )
            field_defs = {f.name: f for f in fd_result.scalars().all()}

            records, idnos = apply_mapping(rows, mapping, field_defs)

            async def store_media_references(
                object_id: uuid.UUID,
                references: list[tuple[str, str]],
            ) -> None:
                nonlocal media_references_created
                if not references:
                    return
                statement = (
                    insert(MediaImportReference)
                    .values(
                        [
                            {
                                "object_id": object_id,
                                "filename": filename,
                                "normalized_filename": normalized,
                            }
                            for filename, normalized in references
                        ]
                    )
                    .on_conflict_do_nothing(constraint="uq_media_import_references_object_filename")
                    .returning(MediaImportReference.id)
                )
                inserted_ids = (await session.execute(statement)).scalars().all()
                media_references_created += len(inserted_ids)

            # Resolve vocab field values: string → {id, label} by looking up/creating terms
            records = await _resolve_vocab_terms(session, field_defs, records)

            # PID fields are system-managed: CSV values are dropped (PIDs are
            # minted via the UI or automatically on publish, never imported).
            pid_field_names = {name for name, f in field_defs.items() if f.field_type == "pid"}
            for row_idx, meta in enumerate(records):
                for pid_name in pid_field_names:
                    if meta.get(pid_name) not in (None, "", []):
                        meta.pop(pid_name, None)
                        warnings.append(
                            {
                                "row": row_idx + 1,
                                "warning": (
                                    f"PID-Feld '{pid_name}' wird beim Import ignoriert – "
                                    "PIDs werden vom System vergeben."
                                ),
                            }
                        )

            # Load idno schema once
            cfg_result = await session.execute(
                select(AdminConfig).where(AdminConfig.key == "default")
            )
            cfg = cfg_result.scalar_one_or_none()
            idno_schema = (cfg.idno_schemas or {}).get(record_type) if cfg else None

            # Build lookup of existing records by idno for upsert
            existing_by_idno: dict[str, Any] = {}
            idnos_to_lookup = [row_idno for row_idno in idnos if row_idno]
            if idnos_to_lookup:
                result = await session.execute(select(model).where(model.idno.in_(idnos_to_lookup)))
                for rec in cast(list[Object | Entity | Place | Occurrence], result.scalars().all()):
                    if rec.idno:
                        existing_by_idno[rec.idno] = rec

            total = len(records)

            for i, metadata in enumerate(records):
                row_num = i + 1
                self.update_state(
                    state="STARTED",
                    meta={"current": i + 1, "total": total, "stage": "importing"},
                )
                if i % 10 == 0 and _is_cancelled():
                    warnings.append({"row": None, "warning": "Import wurde abgebrochen."})
                    break

                # Determine idno
                row_idno = idnos[i] if i < len(idnos) else None
                idno: str | None = None
                if has_idno_column and row_idno:
                    idno = row_idno
                elif idno_strategy == "auto" and idno_schema:
                    idno = await consume_next_idno(session, record_type, idno_schema)

                # Handle upsert
                existing = existing_by_idno.get(idno) if idno else None
                if existing:
                    if upsert_strategy == "skip":
                        await store_media_references(existing.id, media_references[i])
                        skipped += 1
                        continue

                    try:
                        async with session.begin_nested():
                            await enforce_not_blocked(session, record_type, existing.id, user)
                            await enforce_not_locked(session, record_type, existing.id, user)
                            old_meta = existing.metadata_ or {}
                            if upsert_strategy == "merge":
                                final_metadata = {
                                    **old_meta,
                                    **{
                                        key: value
                                        for key, value in metadata.items()
                                        if key not in old_meta
                                    },
                                }
                            else:
                                final_metadata = {**old_meta, **metadata}
                            final_metadata = await prepare_metadata(
                                session,
                                record_type,
                                final_metadata,
                                subtype,
                                existing=old_meta,
                                can_edit_locked=can_edit_locked,
                            )
                            val_errors = await validate_metadata(
                                session, record_type, final_metadata, subtype, skip_required=True
                            )
                            if val_errors:
                                errors.append({"row": row_num, "error": "; ".join(val_errors)})
                                continue

                            old_fields = {"metadata": old_meta}
                            new_fields = {"metadata": final_metadata}
                            existing.metadata_ = final_metadata
                            if upsert_strategy == "replace" and subtype_field:
                                old_fields[subtype_field] = getattr(existing, subtype_field)
                                new_fields[subtype_field] = subtype
                                setattr(existing, subtype_field, subtype)
                            await session.flush()
                            await sync_schema_relations(
                                session, record_type, existing.id, final_metadata
                            )
                            update_diff = diff_fields(old_fields, new_fields)
                            if update_diff:
                                await log_change(
                                    session,
                                    record_type=record_type,
                                    record_id=existing.id,
                                    user_id=user_uuid,
                                    action="update",
                                    changed_fields=update_diff,
                                )
                    except StaleDataError:
                        skipped += 1
                        warnings.append(
                            {
                                "row": row_num,
                                "warning": (
                                    "Datensatz wurde zwischenzeitlich geändert "
                                    "(Version-Konflikt) – Zeile übersprungen."
                                ),
                            }
                        )
                        continue
                    except HTTPException as exc:
                        skipped += 1
                        errors.append({"row": row_num, "error": str(exc.detail)})
                        continue

                    updated += 1
                    await store_media_references(existing.id, media_references[i])
                    try:
                        await index_record(record_type, existing, session)
                    except Exception as e:
                        index_failed += 1
                        warnings.append(
                            {"row": row_num, "warning": f"ES-Indexierung fehlgeschlagen: {e}"}
                        )

                    if auto_publish:
                        pub_result = await publish_record(
                            session, record_type, str(existing.id), user_id
                        )
                        if pub_result["ok"]:
                            published += 1
                        else:
                            publish_failed += 1
                            for reason in pub_result.get("errors") or []:
                                if (
                                    reason not in publish_fail_reasons
                                    and len(publish_fail_reasons) < 5
                                ):
                                    publish_fail_reasons.append(reason)
                    continue

                metadata = await prepare_metadata(
                    session,
                    record_type,
                    metadata,
                    subtype,
                    can_edit_locked=can_edit_locked,
                )
                val_errors = await validate_metadata(
                    session, record_type, metadata, subtype, skip_required=True
                )
                if val_errors:
                    errors.append({"row": row_num, "error": "; ".join(val_errors)})
                    continue

                kwargs: dict[str, Any] = {
                    "metadata_": metadata,
                    "status": "draft",
                }
                if idno:
                    kwargs["idno"] = idno
                if subtype_field:
                    kwargs[subtype_field] = subtype

                rec = model(**kwargs)
                session.add(rec)
                await session.flush()
                await sync_schema_relations(session, record_type, rec.id, metadata)
                created += 1
                await store_media_references(rec.id, media_references[i])

                try:
                    await log_change(
                        session,
                        record_type=record_type,
                        record_id=rec.id,
                        user_id=user_uuid,
                        action="create",
                        changed_fields={"source": "import", "row": row_num},
                    )
                except Exception as e:
                    warnings.append({"row": row_num, "warning": f"Audit-Log fehlgeschlagen: {e}"})

                try:
                    await index_record(record_type, rec, session)
                except Exception as e:
                    index_failed += 1
                    warnings.append(
                        {"row": row_num, "warning": f"ES-Indexierung fehlgeschlagen: {e}"}
                    )

                if auto_publish:
                    pub_result = await publish_record(session, record_type, str(rec.id), user_id)
                    if pub_result["ok"]:
                        published += 1
                    else:
                        publish_failed += 1
                        for reason in pub_result.get("errors") or []:
                            if reason not in publish_fail_reasons and len(publish_fail_reasons) < 5:
                                publish_fail_reasons.append(reason)

            await session.commit()
            await run_after_commit_hooks(session)

        # Trigger bulk reindex for this type so all records are consistently indexed.
        # Runs after the commit above, so the standard swallow-and-log enqueue() is
        # correct here (not after_commit — the session is already closed).
        if created > 0 or updated > 0:
            from katalon.workers.index_tasks import bulk_reindex_type_task

            enqueue(bulk_reindex_type_task, record_type)

        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "published": published,
            "publish_failed": publish_failed,
            "publish_fail_reasons": publish_fail_reasons,
            "index_failed": index_failed,
            "media_references_created": media_references_created,
            "errors": errors,
            "warnings": warnings,
        }

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_import())
        _queue_import_notification(user_id, record_type, result)
        return result
    except Exception:
        _queue_import_notification(user_id, record_type, {"error": "failed"})
        raise
    finally:
        loop.run_until_complete(_engine.dispose())
        loop.close()
