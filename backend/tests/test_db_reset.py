# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Regression tests for database reset configuration preservation."""

from katalon.management.db_reset import _CONFIG_TABLES


def test_data_reset_preserves_permission_configuration() -> None:
    assert {"role_permissions", "feature_permissions"} <= _CONFIG_TABLES
