# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterator
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class SourceKind(StrEnum):
    FIELD = "field"
    RELATION = "relation"
    RECORD = "record"
    CONSTANT = "constant"
    MEDIA = "media"


class MappingDiagnostic(BaseModel):
    code: str
    message: str
    level: Literal["error", "warning", "info"] = "error"
    target_key: str | None = None
    rule_key: uuid.UUID | None = None

class LocalizedText(BaseModel):
    de: str
    en: str


class ExportTargetCapability(BaseModel):
    key: str
    group: str
    label: LocalizedText
    help: LocalizedText
    source_kinds: set[SourceKind] = Field(default_factory=lambda: {SourceKind.FIELD})
    accepted_field_types: set[str] = Field(default_factory=set)
    cardinality: Literal["one", "many"] = "many"
    required: bool = False
    editor_kind: str = "default"
    settings_schema: dict[str, Any] = Field(default_factory=dict)


class ValidatorDependency(BaseModel):
    name: str
    version: str | None = None
    available: bool = True


class ExportProfileCapabilities(BaseModel):
    format_key: str
    profile_id: str
    profile_version: str
    label: LocalizedText
    targets: list[ExportTargetCapability]
    validators: list[ValidatorDependency] = Field(default_factory=list)
    loss_boundaries: list[LocalizedText] = Field(default_factory=list)


class MappingSpec(BaseModel):
    rule_key: uuid.UUID = Field(default_factory=uuid.uuid4)
    source_kind: SourceKind = SourceKind.FIELD
    source_config: dict[str, Any] = Field(default_factory=dict)
    target_key: str
    settings: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = 0
    is_enabled: bool = True
    @property
    def field_name(self) -> str | None:
        if self.source_kind == SourceKind.FIELD:
            val = self.source_config.get("field_name")
            return str(val) if val is not None else None
        return None


class CompiledMappingSet(BaseModel):
    format_key: str
    record_type: str
    rules: list[MappingSpec] = Field(default_factory=list)

    @classmethod
    def from_legacy_dict(
        cls,
        format_key: str,
        record_type: str,
        legacy: dict[str, list[str]] | None,
    ) -> CompiledMappingSet:
        rules: list[MappingSpec] = []
        if legacy:
            for sort_order, (field_name, targets) in enumerate(legacy.items()):
                for target in targets:
                    rules.append(
                        MappingSpec(
                            rule_key=uuid.uuid4(),
                            source_kind=SourceKind.FIELD,
                            source_config={"field_name": field_name},
                            target_key=target,
                            settings={},
                            sort_order=sort_order,
                            is_enabled=True,
                        )
                    )
        return cls(format_key=format_key, record_type=record_type, rules=rules)

    def by_field(self) -> dict[str, list[str]]:
        """Return field_name -> list of target_keys for backward compatibility."""
        res: dict[str, list[str]] = defaultdict(list)
        for rule in self.rules:
            if not rule.is_enabled:
                continue
            fname = rule.field_name
            if fname:
                res[fname].append(rule.target_key)
        return dict(res)

    def by_target(self) -> dict[str, list[MappingSpec]]:
        """Return target_key -> list of rules."""
        res: dict[str, list[MappingSpec]] = defaultdict(list)
        for rule in self.rules:
            if rule.is_enabled:
                res[rule.target_key].append(rule)
        return dict(res)

    # Mapping/dict protocol methods for seamless backwards compatibility
    def items(self) -> list[tuple[str, list[str]]]:
        return list(self.by_field().items())

    def keys(self) -> list[str]:
        return list(self.by_field().keys())

    def values(self) -> list[list[str]]:
        return list(self.by_field().values())

    def get(self, key: str, default: Any = None) -> Any:
        return self.by_field().get(key, default)

    def __getitem__(self, key: str) -> list[str]:
        return self.by_field()[key]

    def __contains__(self, key: object) -> bool:
        return key in self.by_field()

    def __len__(self) -> int:
        return len(self.by_field())

    def __iter__(self) -> Iterator[str]:
        return iter(self.by_field())


class MetadataFormat(ABC):
    key: str
    label: str
    targets: set[str]
    schema_url: str
    namespace: str
    def capabilities(self) -> ExportProfileCapabilities:
        """Return the capability profile for this format."""
        return ExportProfileCapabilities(
            format_key=self.key,
            profile_id=f"{self.key}_default",
            profile_version="1.0",
            label=LocalizedText(de=self.label, en=self.label),
            targets=[
                ExportTargetCapability(
                    key=target,
                    group="default",
                    label=LocalizedText(de=target, en=target),
                    help=LocalizedText(de="", en=""),
                    source_kinds={SourceKind.FIELD},
                )
                for target in sorted(self.targets)
            ],
        )

    def validate_mapping(self, mapping_set: CompiledMappingSet) -> list[MappingDiagnostic]:
        """Validate a compiled mapping set against this format's targets and rules."""
        diagnostics: list[MappingDiagnostic] = []
        for rule in mapping_set.rules:
            if rule.target_key not in self.targets:
                diagnostics.append(
                    MappingDiagnostic(
                        code="invalid_target",
                        message=f"Ungültiges {self.label}-Ziel '{rule.target_key}'.",
                        level="error",
                        target_key=rule.target_key,
                        rule_key=rule.rule_key,
                    )
                )
        return diagnostics

    @abstractmethod
    def render(
        self,
        hit: dict[str, Any],
        mappings: CompiledMappingSet | dict[str, list[str]],
    ) -> ET.Element:
        """Render one ES hit into a format-specific XML element."""
def append_path(root: ET.Element, path: str, value: str) -> None:
    """Create the nested element chain for a slash-separated target_path and set the leaf text."""
    if not value:
        return
    parts = path.split("/")
    el = root
    for part in parts[:-1]:
        el = ET.SubElement(el, part)
    ET.SubElement(el, parts[-1]).text = value
