# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import xml.etree.ElementTree as ET

from katalon.integrations.metadata_format import (
    CompiledMappingSet,
    ExportMediaItem,
    ExportRecordContext,
    ExportRecordSummary,
    MappingSpec,
    SourceKind,
)
from katalon.integrations.mets_mods_format import (
    ALL_MODS_TARGETS,
    CORE_MODS_TARGETS,
    OPTIONAL_MODS_TARGETS,
    MetsModsFormat,
)


def _sample_context() -> ExportRecordContext:
    return ExportRecordContext(
        record=ExportRecordSummary(
            id="7dce603c-469d-4bc7-a57a-71dd99112233",
            idno="OBJ-100",
            record_type="object",
            title="Konvolut ungesichteter Notizzettel",
        ),
        fields={
            "title": "Konvolut ungesichteter Notizzettel",
            "creator": "Johann Peter Eckermann",
            "toc": "1. Notiz zu Goethes Gesprächen\n2. Quittung vom Buchhändler",
            "genre": "Manuskript",
            "note": "Aus Nachlass erworben",
            "license": "https://creativecommons.org/licenses/by/4.0/",
        },
        relations=[],
        media=[
            ExportMediaItem(
                id="media-1",
                filename="page1.jpg",
                mime_type="image/jpeg",
                url="https://assets.example.org/page1.jpg",
                license_uri="https://creativecommons.org/publicdomain/zero/1.0/",
                rights_holder="CC0; Katalon Demo",
                rights_holder_uri="https://katalon-collections.github.io",
            )
        ],
    )


def test_mets_mods_capabilities_and_targets() -> None:
    fmt = MetsModsFormat()
    caps = fmt.capabilities()

    assert len(caps.targets) == 20
    assert len(CORE_MODS_TARGETS) == 8
    assert len(OPTIONAL_MODS_TARGETS) == 12
    assert ALL_MODS_TARGETS == CORE_MODS_TARGETS | OPTIONAL_MODS_TARGETS

    targets_by_key = {t.key: t for t in caps.targets}

    # Verify core targets
    for core_key in CORE_MODS_TARGETS:
        assert core_key in targets_by_key
        assert targets_by_key[core_key].is_core is True

    # Verify optional targets
    for opt_key in OPTIONAL_MODS_TARGETS:
        assert opt_key in targets_by_key
        assert targets_by_key[opt_key].is_core is False

    # Verify "Objekt- / Medienlizenz" label and source kinds for accessCondition
    lic_target = targets_by_key["mods:accessCondition"]
    assert lic_target.label.de == "Objekt- / Medienlizenz"
    assert lic_target.label.en == "Object / Media License"
    assert SourceKind.MEDIA in lic_target.source_kinds
    assert SourceKind.FIELD in lic_target.source_kinds
    assert SourceKind.CONSTANT in lic_target.source_kinds

    # Verify mods:subject/mods:topic is classified under "classification"
    subj_target = targets_by_key["mods:subject/mods:topic"]
    assert subj_target.group == "classification"


def test_mets_mods_render_wrapper_structure() -> None:
    fmt = MetsModsFormat()
    ctx = _sample_context()

    cms = CompiledMappingSet(
        format_key="mets_mods",
        record_type="object",
        institution_config={
            "institution_name": "Goethe-Museum",
            "website": "https://goethe-museum.example.org",
        },
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="mods:titleInfo/mods:title",
            ),
        ],
    )

    root = fmt.render(ctx, cms)
    xml_str = ET.tostring(root, encoding="unicode")

    # 1. METS Root Element
    assert root.tag == "mets:mets" or root.tag.endswith("}mets")
    assert root.attrib.get("OBJID") == "OBJ-100"
    assert root.attrib.get("TYPE") == "object"

    # 2. METS Header with institution name
    assert "<mets:metsHdr" in xml_str
    assert "<mets:name>Goethe-Museum</mets:name>" in xml_str

    # 3. Descriptive metadata: DMD section wrapping MODS
    assert '<mets:dmdSec ID="DMD_0001">' in xml_str
    assert '<mets:mdWrap MDTYPE="MODS" MIMETYPE="text/xml">' in xml_str
    assert "<mods:mods" in xml_str
    assert "<mods:title>Konvolut ungesichteter Notizzettel</mods:title>" in xml_str

    # 4. Administrative metadata: AMD section with two rightsMD sections
    assert '<mets:amdSec ID="AMD_0001">' in xml_str
    assert '<mets:rightsMD ID="RIGHTS_MODS_0001">' in xml_str
    assert '<mets:rightsMD ID="RIGHTS_DVRIGHTS_0001">' in xml_str

    # 5. File section for media
    assert "<mets:fileSec>" in xml_str
    assert 'xlink:href="https://assets.example.org/page1.jpg"' in xml_str

    # 6. Single record structural map
    assert '<mets:structMap TYPE="LOGICAL">' in xml_str
    assert '<mets:div ID="LOG_0001" TYPE="object" DMDID="DMD_0001" ADMID="AMD_0001"' in xml_str
    assert 'FILEID="FILE_0001"' in xml_str


def test_mets_mods_license_fills_both_rightsmd_and_mods() -> None:
    fmt = MetsModsFormat()
    ctx = _sample_context()

    cms = CompiledMappingSet(
        format_key="mets_mods",
        record_type="object",
        institution_config={
            "institution_name": "Goethe-Museum",
            "website": "https://goethe-museum.example.org",
        },
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="mods:titleInfo/mods:title",
            ),
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "license"},
                target_key="mods:accessCondition",
            ),
        ],
    )

    root = fmt.render(ctx, cms)
    xml_str = ET.tostring(root, encoding="unicode")

    # mods:accessCondition in MODS descriptive metadata
    assert 'xlink:href="https://creativecommons.org/licenses/by/4.0/"' in xml_str
    # RIGHTS_MODS in amdSec
    assert '<mets:rightsMD ID="RIGHTS_MODS_0001">' in xml_str
    # RIGHTS_DVRIGHTS in amdSec
    assert '<mets:rightsMD ID="RIGHTS_DVRIGHTS_0001">' in xml_str
    assert "<dv:rights" in xml_str
    assert "<dv:owner>Goethe-Museum</dv:owner>" in xml_str
    assert "<dv:ownerSiteURL>https://goethe-museum.example.org</dv:ownerSiteURL>" in xml_str
    assert "<dv:license>https://creativecommons.org/licenses/by/4.0/</dv:license>" in xml_str


def test_mets_mods_optional_top_level_elements() -> None:
    fmt = MetsModsFormat()
    ctx = _sample_context()

    cms = CompiledMappingSet(
        format_key="mets_mods",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="mods:titleInfo/mods:title",
            ),
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "toc"},
                target_key="mods:tableOfContents",
            ),
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "genre"},
                target_key="mods:genre",
            ),
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "note"},
                target_key="mods:note",
            ),
        ],
    )

    root = fmt.render(ctx, cms)
    xml_str = ET.tostring(root, encoding="unicode")

    assert "<mods:tableOfContents>" in xml_str
    assert "1. Notiz zu Goethes Gesprächen" in xml_str
    assert "<mods:genre>Manuskript</mods:genre>" in xml_str
    assert "<mods:note>Aus Nachlass erworben</mods:note>" in xml_str


def test_mets_mods_batch_envelope() -> None:
    fmt = MetsModsFormat()
    ctx = _sample_context()
    cms = CompiledMappingSet(
        format_key="mets_mods",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="mods:titleInfo/mods:title",
            ),
        ],
    )

    start_env, end_env = fmt.render_batch_envelope()
    assert "<mets:metsCollection" in start_env
    assert "</mets:metsCollection>" in end_env

    item = fmt.render_batch_item(ctx, cms)
    item_str = ET.tostring(item, encoding="unicode")
    assert "<mets:mets" in item_str
    assert "OBJ-100" in item_str


def test_mets_mods_note_with_type_attribute() -> None:
    fmt = MetsModsFormat()
    ctx = _sample_context()
    cms = CompiledMappingSet(
        format_key="mets_mods",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="mods:titleInfo/mods:title",
            ),
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "note"},
                target_key="mods:note",
                settings={"type": "ownership"},
            ),
        ],
    )

    root = fmt.render(ctx, cms)
    xml_str = ET.tostring(root, encoding="unicode")
    assert '<mods:note type="ownership">Aus Nachlass erworben</mods:note>' in xml_str


def test_mets_mods_license_derived_from_media_fallback() -> None:
    """When no accessCondition rule is mapped, license and rights holder are derived from ctx.media."""
    fmt = MetsModsFormat()
    ctx = _sample_context()
    cms = CompiledMappingSet(
        format_key="mets_mods",
        record_type="object",
        institution_config={
            "institution_name": "Goethe-Museum",
            "website": "https://goethe-museum.example.org",
        },
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="mods:titleInfo/mods:title",
            ),
        ],
    )

    root = fmt.render(ctx, cms)
    xml_str = ET.tostring(root, encoding="unicode")

    # 1. mods:mods in dmdSec contains derived accessCondition
    assert '<mods:accessCondition type="use and reproduction" xlink:href="https://creativecommons.org/publicdomain/zero/1.0/">https://creativecommons.org/publicdomain/zero/1.0/</mods:accessCondition>' in xml_str

    # 2. RIGHTS_MODS in amdSec contains derived accessCondition
    assert '<mets:rightsMD ID="RIGHTS_MODS_0001">' in xml_str

    # 3. RIGHTS_DVRIGHTS in amdSec contains institution owner and media license
    assert '<mets:rightsMD ID="RIGHTS_DVRIGHTS_0001">' in xml_str
    assert "<dv:rights>" in xml_str
    assert "<dv:owner>Goethe-Museum</dv:owner>" in xml_str
    assert "<dv:ownerSiteURL>https://goethe-museum.example.org</dv:ownerSiteURL>" in xml_str
    assert "<dv:license>https://creativecommons.org/publicdomain/zero/1.0/</dv:license>" in xml_str


def test_mets_mods_license_explicit_media_mapping() -> None:
    """When accessCondition is explicitly mapped to SourceKind.MEDIA license_uri."""
    fmt = MetsModsFormat()
    ctx = _sample_context()
    cms = CompiledMappingSet(
        format_key="mets_mods",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="mods:titleInfo/mods:title",
            ),
            MappingSpec(
                source_kind=SourceKind.MEDIA,
                source_config={"property": "license_uri"},
                target_key="mods:accessCondition",
            ),
        ],
    )

    root = fmt.render(ctx, cms)
    xml_str = ET.tostring(root, encoding="unicode")

    assert '<mods:accessCondition type="use and reproduction" xlink:href="https://creativecommons.org/publicdomain/zero/1.0/">https://creativecommons.org/publicdomain/zero/1.0/</mods:accessCondition>' in xml_str
    assert "<dv:owner>Katalon</dv:owner>" in xml_str
    assert "<dv:license>https://creativecommons.org/publicdomain/zero/1.0/</dv:license>" in xml_str


def test_mets_mods_multiple_notes_with_subkeys() -> None:
    """Verify that multiple notes (with mods:note and mods:note/...) validate and render distinct tags."""
    fmt = MetsModsFormat()
    ctx = _sample_context()
    cms = CompiledMappingSet(
        format_key="mets_mods",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="mods:titleInfo/mods:title",
            ),
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "note"},
                target_key="mods:note",
                settings={"type": "general"},
            ),
            MappingSpec(
                source_kind=SourceKind.CONSTANT,
                source_config={"value": "Schenkung aus Privatbesitz 1920"},
                target_key="mods:note/ownership_1",
                settings={"type": "ownership"},
            ),
        ],
    )

    # 1. Validation succeeds with 0 diagnostics
    diags = fmt.validate_mapping(cms)
    assert len(diags) == 0

    # 2. Both note tags appear in render
    root = fmt.render(ctx, cms)
    xml_str = ET.tostring(root, encoding="unicode")
    assert '<mods:note type="general">Aus Nachlass erworben</mods:note>' in xml_str
    assert '<mods:note type="ownership">Schenkung aus Privatbesitz 1920</mods:note>' in xml_str


