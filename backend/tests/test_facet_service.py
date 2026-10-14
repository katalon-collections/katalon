# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Date buckets for EDTF-lite values (patterns from the BPK data) and facet order."""

import pytest

from katalon.services.facet_service import apply_order, date_buckets


@pytest.mark.parametrize(
    ("value", "granularity", "expected"),
    [
        ("1918-03-21", "decade", ["1910"]),
        ("1918-03-21", "century", ["1900"]),
        ("1918-03-21", "year", ["1918"]),
        ("1890/", "decade", ["1890"]),  # open end: start bucket only
        ("/1905", "decade", ["1900"]),  # open start: end bucket only
        ("1912", "decade", ["1910"]),
        ("1884/1919", "decade", ["1880", "1890", "1900", "1910"]),
        ("1911~", "decade", ["1910"]),
        ("1913-05", "decade", ["1910"]),
        ("1914-08-01/1918-11-11", "decade", ["1910"]),
        ("1912~/1916", "decade", ["1910"]),
        ("1898~/1905~", "decade", ["1890", "1900"]),
        ("1902-02-02/", "decade", ["1900"]),
        # Longer than DATE_SPAN_MAX_DECADES: only start and end bucket.
        ("1850/1950", "decade", ["1850", "1950"]),
    ],
)
def test_date_buckets_for_bpk_patterns(value, granularity, expected) -> None:
    buckets, rejected = date_buckets([value], granularity)
    assert buckets == expected
    assert rejected == []


def test_implausible_and_empty_values_are_ignored() -> None:
    buckets, rejected = date_buckets(["0196-11-26", "", "3020", "1925-01-01"], "decade")
    assert buckets == ["1920"]
    assert rejected == ["0196-11-26", "3020"]


def test_values_from_several_group_instances_are_merged_and_sorted() -> None:
    buckets, _ = date_buckets(["1921-01-01", "1899", "1923/1924"], "decade")
    assert buckets == ["1890", "1920"]


def test_apply_order_puts_configured_names_first() -> None:
    assert apply_order(["a", "b", "c", "d"], ["c", "x", "a"]) == ["c", "a", "b", "d"]
    assert apply_order(["a", "b"], None) == ["a", "b"]
