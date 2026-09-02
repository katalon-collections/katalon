# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Application-level exceptions.

Kept free of imports from katalon.config / database so that this module can be
pulled in by entry scripts without evaluating a full Settings object.
"""


class KatalonSecretsKeyError(RuntimeError):
    """Raised when KATALON_SECRETS_KEY is missing or shorter than 32 characters."""
