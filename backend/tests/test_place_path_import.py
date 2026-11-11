# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import pytest

from katalon.api.v1.importer import MappingEntry, _normalize_mapping
from katalon.services.place_path_import import place_path_separator, split_path


def test_split_path_trims_and_rejects_empty_levels() -> None:
    assert split_path("Deutschland > Mecklenburg-Vorpommern>Schwerin", ">") == [
        "Deutschland",
        "Mecklenburg-Vorpommern",
        "Schwerin",
    ]
    assert split_path("Schwerin", ">") == ["Schwerin"]
    with pytest.raises(ValueError):
        split_path("A>>B", ">")


def test_path_separator_survives_mapping_normalization() -> None:
    raw = {"col": MappingEntry(target="label", path_separator=">"), "id": MappingEntry(target="x")}
    normalized = _normalize_mapping(raw)
    assert place_path_separator(normalized) == ">"
    assert "path_separator" not in normalized["id"]
    # stored mappings (plain dicts) keep it as well
    assert _normalize_mapping({"c": {"target": "label", "path_separator": "/"}})["c"][
        "path_separator"
    ] == "/"
    assert place_path_separator({"c": {"target": "label"}}) is None
