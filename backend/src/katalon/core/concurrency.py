"""Optimistic locking helper for record updates.

Records carry a monotonically increasing ``version``. A client that loaded a
record at version N sends ``If-Match: N`` on update. If the stored version has
moved on (someone else saved in the meantime), we refuse with 409 instead of
silently overwriting their change (last-write-wins).

The check is only enforced when the client supplies ``If-Match`` — scripts and
the importer that do not send it keep their previous behaviour; the admin UI
always sends it.
"""

from fastapi import HTTPException


def check_version(current_version: int, if_match: int | None) -> None:
    """Raise 409 if the client's expected version no longer matches the record.

    On mismatch the client re-fetches the current server state and resolves the
    conflict (see the admin UI merge dialog).
    """
    if if_match is not None and if_match != current_version:
        raise HTTPException(
            status_code=409,
            detail={"error": "version_conflict", "current_version": current_version},
        )
