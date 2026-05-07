from uuid import UUID

import pytest

from katalon.services.pid_service import register_dnb_urn_for_record


@pytest.mark.asyncio
async def test_register_dnb_urn_restricted_to_objects() -> None:
    with pytest.raises(ValueError, match="nur für Objekte erlaubt"):
        await register_dnb_urn_for_record(
            db=None,  # type: ignore[arg-type]
            record_type="entity",
            record_id=UUID("00000000-0000-0000-0000-000000000001"),
            field_name="urn",
            target_url="https://example.org/record/entity/1",
            label="URN",
        )
