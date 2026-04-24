"""REST routes for research sessions.

The React frontend calls these for initial state and mutations. Real-time
updates still come over GraphQL subscriptions from the Cosmo Router.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, status

from ..context_engine import query_session_context, related_session_context
from ..redis_client import (
    list_sessions as redis_list_sessions,
    load_session,
    publish_collaborator_event,
    read_run_incidents,
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
    utcnow_iso,
)
from ..tinyfish_runner import run_agent_for_session

log = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


DEFAULT_SEED_URLS: dict[str, str] = {
    "ai chip supply chain": "https://medium.com/@gaetanlion/the-ai-chips-supply-chain-incredible-fragility-6d6a7197b3c5",
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
        useTwoPhase=req.useTwoPhase,
        maxDiscoverUrls=req.maxDiscoverUrls,
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
    asyncio.create_task(
        _safe_run(
            session_id,
            req.topic,
            seed_url,
            use_two_phase=req.useTwoPhase,
            max_discover_urls=req.maxDiscoverUrls,
        )
    )

    return session


async def _safe_run(
    session_id: str,
    topic: str,
    seed_url: str,
    *,
    use_two_phase: bool,
    max_discover_urls: int,
) -> None:
    try:
        await run_agent_for_session(
            session_id,
            topic,
            seed_url,
            use_two_phase=use_two_phase,
            max_discover_urls=max_discover_urls,
        )
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


@router.get("/{session_id}/final-report")
async def get_final_report(session_id: str) -> dict[str, Any]:
    """Build a stable final report from canonical papers for popup download."""
    session = await load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    papers, incidents, context = await asyncio.gather(
        read_session_papers(session_id),
        read_run_incidents(session_id),
        related_session_context(session_id),
    )
    papers.sort(key=_paper_rank, reverse=True)
    markdown = _build_markdown_report(session.topic, papers, context, incidents)

    # Keep sources deduplicated so the popup can show crawl provenance.
    source_urls = [p.sourceUrl for p in papers if p.sourceUrl]
    deduped_sources = sorted(set(source_urls))
    is_empty = len(papers) == 0
    if is_empty and incidents:
        unique: list[str] = []
        seen: set[str] = set()
        for i in incidents:
            s = str(i.get("summary", "")).strip()
            if s and s not in seen:
                seen.add(s)
                unique.append(s)
        empty_reason = (
            " · ".join(unique[:4])
            if unique
            else "No extractable papers were stored; see the report markdown for per-URL details."
        )
    elif is_empty:
        empty_reason = (
            "No normalized papers are available yet. The agent may have completed, "
            "but the normalizer worker might still be processing (or not running)."
        )
    else:
        empty_reason = None
    return {
        "sessionId": session_id,
        "generatedAt": utcnow_iso(),
        "summary": {
            "topic": session.topic,
            "paperCount": len(papers),
            "sourceCount": len(deduped_sources),
        },
        "papers": [paper.model_dump(mode="json") for paper in papers[:25]],
        "sources": [
            {"url": url, "domain": _domain(url)}
            for url in deduped_sources[:50]
        ],
        "context": context[:8],
        "incidents": incidents,
        "markdown": markdown,
        "isEmpty": is_empty,
        "emptyReason": empty_reason,
    }


def _paper_rank(paper: Any) -> tuple[float, int, int]:
    """Sort by confidence, findings, and citation chain richness."""
    confidence = float(getattr(paper, "confidence", 0.0) or 0.0)
    findings = len(getattr(paper, "keyFindings", []) or [])
    graph_degree = len(getattr(paper, "references", []) or []) + len(getattr(paper, "citedBy", []) or [])
    return (confidence, findings, graph_degree)


def _build_markdown_report(
    topic: str,
    papers: list[Any],
    context: list[dict[str, Any]],
    incidents: list[dict[str, Any]] | None = None,
) -> str:
    lines: list[str] = []
    incidents = incidents or []
    lines.append(f"# Final Research Report: {topic}")
    lines.append("")
    lines.append(f"Generated from {len(papers)} normalized papers.")
    lines.append("")

    if not papers:
        lines.append("## Report status")
        if incidents:
            lines.append(
                "- No normalized papers are in session storage, but the agent "
                "recorded per-URL outcomes below (blocked page, error, or empty extraction)."
            )
            lines.append(
                "- If a source was protected by anti-bot (e.g. Cloudflare) or a CAPTCHA, "
                "that is a site-level constraint, not a missing normalizer alone."
            )
        else:
            lines.append(
                "- No normalized papers are currently available for this session."
            )
            lines.append(
                "- Check that the normalizer worker is running and consuming Redis stream messages."
            )
        if incidents:
            lines.append("")
            lines.append("## Extraction issues")
            for it in incidents[:50]:
                u = (it.get("sourceUrl") or "").strip()
                s = (it.get("summary") or "").strip()
                k = (it.get("kind") or "empty").strip()
                head = f"**{k}**" if k else "Issue"
                if u and s:
                    lines.append(f"- {head}: {s} — `{u}`")
                elif s:
                    lines.append(f"- {head}: {s}")
        return "\n".join(lines)

    lines.append("## Key findings")
    any_finding = False
    for paper in papers[:8]:
        for finding in (paper.keyFindings or [])[:2]:
            any_finding = True
            lines.append(f"- {finding} _(source: {paper.title})_")
    if not any_finding:
        lines.append("- No explicit key findings were extracted.")
    lines.append("")

    lines.append("## Papers")
    for paper in papers[:12]:
        id_bits = []
        if paper.doi:
            id_bits.append(f"doi:{paper.doi}")
        if paper.arxivId:
            id_bits.append(f"arXiv:{paper.arxivId}")
        id_suffix = f" ({', '.join(id_bits)})" if id_bits else ""
        venue_bits = []
        if paper.venue:
            venue_bits.append(paper.venue)
        if paper.year:
            venue_bits.append(str(paper.year))
        venue_line = " | ".join(venue_bits) if venue_bits else "Unknown venue/year"
        lines.append(f"- **{paper.title}**{id_suffix}")
        lines.append(f"  - Venue: {venue_line}")
        if paper.authors:
            lines.append(f"  - Authors: {', '.join(paper.authors[:8])}")
        if paper.methodology:
            lines.append(f"  - Methodology: {paper.methodology}")
        if paper.references:
            lines.append(f"  - References ({min(5, len(paper.references))}): {', '.join(paper.references[:5])}")
        if paper.citedBy:
            lines.append(f"  - Cited by ({min(5, len(paper.citedBy))}): {', '.join(paper.citedBy[:5])}")
        if paper.sourceUrl:
            lines.append(f"  - Source URL: {paper.sourceUrl}")
    lines.append("")

    if context:
        lines.append("## Related context")
        for item in context[:5]:
            title = item.get("title") or item.get("paperId") or "Related context item"
            lines.append(f"- {title}")
        lines.append("")

    lines.append("## Notes")
    lines.append("- This report is generated from canonical paper records in session storage.")
    lines.append("- If this report is sparse, rerun after the normalizer worker has processed more data.")
    return "\n".join(lines)


def _domain(url: str) -> str:
    try:
        return urlparse(url).hostname or url
    except Exception:
        return url
