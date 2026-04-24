"""REST routes exposing the TinyFish agent state to the frontend."""

from __future__ import annotations

from fastapi import APIRouter

from ..redis_client import get_streaming_url

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/{session_id}/snapshot-url")
async def get_snapshot_url(session_id: str) -> dict[str, str | None]:
    """Return the cached TinyFish streaming_url for the session.

    The frontend polls this once a few seconds after starting a session and
    drops the URL in an iframe. Falls back to None during mock mode.
    """
    url = await get_streaming_url(session_id)
    return {"streamingUrl": url}
