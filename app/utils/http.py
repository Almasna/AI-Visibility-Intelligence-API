from __future__ import annotations

from uuid import UUID

from app.utils.errors import ApiError


def canonical_uuid(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise ApiError("INVALID_UUID", "The resource UUID is invalid.", 400) from exc
