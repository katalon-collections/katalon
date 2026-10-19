# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Exports must not depend on the process or on the index copy (API preview vs. worker/OAI)."""

import uuid
from types import SimpleNamespace

from katalon.integrations.lido.builder import _authority_ids
from katalon.services.public_metadata_service import filter_public_metadata

GND = "https://d-nb.info/gnd/4005728-8"
VIAF = "http://viaf.org/viaf/122530980"


def _field(name: str, *, parent_id: uuid.UUID | None = None, field_type: str = "text") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), name=name, parent_id=parent_id, field_type=field_type, target_subtype=None
    )


def test_filter_public_metadata_keeps_schema_order_of_group_children() -> None:
    group = _field("normdaten", field_type="group")
    fields = [group, _field("ag_gnd", parent_id=group.id), _field("ag_viaf", parent_id=group.id)]
    stored = {"normdaten": [{"ag_viaf": {"value": VIAF}, "ag_gnd": {"value": GND}}]}

    projected = filter_public_metadata(stored, fields)

    assert list(projected["normdaten"][0]) == ["ag_gnd", "ag_viaf"]


def test_authority_ids_group_is_independent_of_key_order() -> None:
    entries = [
        {"ag_gnd": {"value": GND}, "ag_viaf": {"value": VIAF}},
        {"ag_viaf": {"value": VIAF}, "ag_gnd": {"value": GND}},
    ]
    id_fields = [{"field": "normdaten", "source": "gnd"}]

    results = [sorted(_authority_ids({"normdaten": [entry]}, id_fields)) for entry in entries]

    assert results[0] == results[1] == sorted([(GND, "gnd"), (VIAF, "viaf")])


def test_authority_ids_addresses_group_sub_field() -> None:
    values = {"normdaten": [{"ag_viaf": {"value": VIAF}, "ag_gnd": {"value": GND}}]}

    assert _authority_ids(values, [{"field": "normdaten.ag_gnd", "source": "gnd"}]) == [(GND, "gnd")]
    assert _authority_ids(values, [{"field": "normdaten.ag_viaf"}]) == [(VIAF, "viaf")]


def test_index_context_from_older_katalon_is_stale() -> None:
    from katalon.integrations.metadata_format import EXPORT_CONTEXT_VERSION
    from katalon.services.export_context_service import index_context_is_stale

    current = {"record": {}, "schema_version": EXPORT_CONTEXT_VERSION}
    assert not index_context_is_stale(current)
    assert index_context_is_stale({"record": {}})  # written before versioning
    assert index_context_is_stale({**current, "schema_version": EXPORT_CONTEXT_VERSION - 1})
    assert index_context_is_stale({**current, "inbound_relations_omitted": 3})
    assert not index_context_is_stale(None)


async def test_resolve_record_id_accepts_uuid_and_inventory_number() -> None:
    from unittest.mock import AsyncMock, MagicMock

    import pytest

    from katalon.services.export_context_service import resolve_record_id

    record_id = uuid.uuid4()
    found = MagicMock(scalar_one_or_none=MagicMock(return_value=record_id))
    db = MagicMock(execute=AsyncMock(return_value=found))
    assert await resolve_record_id(db, "object", str(record_id)) == record_id
    db.execute.assert_not_awaited()  # a UUID needs no lookup
    assert await resolve_record_id(db, "object", " os_ub_0031153 ") == record_id

    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    with pytest.raises(ValueError, match="Inventarnummer"):
        await resolve_record_id(db, "object", "gibt-es-nicht")


def test_oai_dc_maps_group_sub_fields_and_strips_rich_text() -> None:
    import xml.etree.ElementTree as ET

    from katalon.integrations.metadata_format import (
        CompiledMappingSet,
        ExportRecordContext,
        ExportRecordSummary,
        MappingSpec,
    )
    from katalon.integrations.oai_dc_format import DC_NS, OaiDcFormat

    ctx = ExportRecordContext(
        record=ExportRecordSummary(id="x", record_type="object", title="T"),
        fields={
            "date": [{"dates_value": "1905/", "dc_dates_types": {"label": "Datierung"}}],
            "bildbeschreibung": "<p>Ein Mann mit Axt.</p><p>Am Himmel Wolken.</p>",
            "schlagwort": [{"label": "Volkslied < deutsch >"}],
        },
    )
    rules = [
        MappingSpec(target_key="dc:date", source_config={"field_name": "date.dates_value"}),
        MappingSpec(target_key="dc:description", source_config={"field_name": "bildbeschreibung"}),
        MappingSpec(target_key="dc:subject", source_config={"field_name": "schlagwort"}),
    ]
    cms = CompiledMappingSet(format_key="oai_dc", record_type="object", rules=rules)

    dc = ET.fromstring(ET.tostring(OaiDcFormat().render(ctx, cms)))

    assert dc.findtext(f"{{{DC_NS}}}date") == "1905/"
    assert dc.findtext(f"{{{DC_NS}}}description") == "Ein Mann mit Axt. Am Himmel Wolken."
    assert dc.findtext(f"{{{DC_NS}}}subject") == "Volkslied < deutsch >"
