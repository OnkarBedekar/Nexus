"""REST routes for research sessions.

The React frontend calls these for initial state and mutations. Real-time
updates still come over GraphQL subscriptions from the Cosmo Router.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status

from ..context_engine import query_session_context, related_session_context
from ..redis_client import (
    list_sessions as redis_list_sessions,
    load_session,
    publish_collaborator_event,
    read_timeline,
    read_session_papers,
    save_session,
    upsert_canonical_paper,
)
from ..schemas import (
    ResearchSession,
    SessionCollaboratorEvent,
    SessionStats,
    SessionStatus,
    StartSessionRequest,
)
from ..tinyfish_runner import run_agent_for_session

log = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


DEFAULT_SEED_URLS: dict[str, str] = {
    "ai chip supply chain": "https://en.wikipedia.org/wiki/TSMC",
    "quantum computing": "https://en.wikipedia.org/wiki/Quantum_computing",
    "carbon capture": "https://en.wikipedia.org/wiki/Carbon_capture_and_storage",
}


def _default_seed_url(topic: str) -> str:
    needle = topic.strip().lower()
    for key, url in DEFAULT_SEED_URLS.items():
        if key in needle:
            return url
    # Wikipedia search always resolves something sensible.
    slug = topic.strip().replace(" ", "_")
    return f"https://en.wikipedia.org/wiki/{slug}"


@router.post("", status_code=status.HTTP_201_CREATED)
async def start_session(req: StartSessionRequest) -> ResearchSession:
    """Create a new research session and kick off the agent run in the background."""
    session_id = uuid.uuid4().hex[:12]
    seed_url = req.seedUrl or _default_seed_url(req.topic)
    session = ResearchSession(
        id=session_id,
        topic=req.topic,
        status=SessionStatus.active,
        stats=SessionStats(),
        seedUrl=seed_url,
        collaborators=req.collaborators,
    )
    await save_session(session)
    if req.rehydrateFromSessionId:
        prior = await read_session_papers(req.rehydrateFromSessionId)
        for paper in prior:
            await upsert_canonical_paper(session_id, paper)
        log.info("Rehydrated %d papers into session %s", len(prior), session_id)
    for collaborator in req.collaborators:
        await publish_collaborator_event(
            session_id,
            SessionCollaboratorEvent(
                sessionId=session_id,
                collaborator=collaborator,
                action="joined",
            ),
        )

    # Run the agent as a background task so the HTTP response returns immediately.
    # We intentionally don't await the task - FastAPI will keep the event loop alive.
    asyncio.create_task(_safe_run(session_id, req.topic, seed_url))

    return session


async def _safe_run(session_id: str, topic: str, seed_url: str) -> None:
    try:
        await run_agent_for_session(session_id, topic, seed_url)
    except Exception:
        log.exception("Background agent task crashed for %s", session_id)


@router.get("")
async def list_sessions() -> list[ResearchSession]:
    sessions = await redis_list_sessions()
    # Newest first
    sessions.sort(key=lambda s: s.startedAt, reverse=True)
    return sessions


@router.get("/{session_id}")
async def get_session(session_id: str) -> ResearchSession:
    session = await load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/{session_id}/pause")
async def pause_session(session_id: str) -> ResearchSession:
    session = await load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = SessionStatus.paused
    await save_session(session)
    # TODO: if live TinyFish is running, POST /v1/runs/{runId}/cancel.
    # Deferred for hackathon scope; the mock runner is a one-shot coroutine.
    return session


@router.get("/{session_id}/timeline")
async def get_timeline(session_id: str) -> list[dict[str, Any]]:
    """Return the full TimelineEvent sequence for replay mode."""
    return await read_timeline(session_id)


@router.get("/{session_id}/rehydrate")
async def rehydrate_session(session_id: str) -> dict[str, Any]:
    """Return canonical papers discovered in this session for fast warm start."""
    papers = await read_session_papers(session_id)
    return {"sessionId": session_id, "papers": [paper.model_dump(mode="json") for paper in papers]}


@router.post("/{session_id}/collaborators/{name}")
async def add_collaborator(session_id: str, name: str) -> ResearchSession:
    session = await load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if name not in session.collaborators:
        session.collaborators.append(name)
        await save_session(session)
        await publish_collaborator_event(
            session_id,
            SessionCollaboratorEvent(
                sessionId=session_id,
                collaborator=name,
                action="joined",
            ),
        )
    return session


@router.get("/{session_id}/context")
async def get_session_context(session_id: str, query: str) -> dict[str, Any]:
    session = await load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    results = await query_session_context(session_id, query)
    return {"sessionId": session_id, "query": query, "results": results}


@router.get("/{session_id}/related")
async def get_related_context(session_id: str) -> dict[str, Any]:
    session = await load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    results = await related_session_context(session_id)
    return {"sessionId": session_id, "results": results}
