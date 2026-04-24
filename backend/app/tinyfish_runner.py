"""The core agent loop.

For each session, we either:

  * Call `AsyncTinyFish.agent.stream(...)` with our `output_schema` and
    relay the Agent SSE events (STREAMING_URL, PROGRESS, COMPLETE) to
    Redis streams/pub-sub for normalization + realtime updates.

  * Or, when MOCK_TINYFISH=1, run a deterministic fake stream against
    an in-memory entity catalog so the UI is fully demoable without API keys.

TinyFish SDK reference (https://docs.tinyfish.ai/agent-api/reference):
    Events emitted by `agent.stream()` are instances of StartedEvent,
    StreamingUrlEvent, ProgressEvent, HeartbeatEvent, CompleteEvent.
    `CompleteEvent.result` contains the structured output validated
    against our `output_schema`.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any
from urllib.parse import urlparse

from .config import get_settings
from .entity_hash import entity_id, relationship_id
from .mock_stream import run_mock_agent
from .normalization import normalize_paper_record
from .parsers import paper_to_entity_claims
from .redis_client import (
    enqueue_raw_extraction,
    load_session,
    mark_url_visited,
    publish_agent_status,
    publish_collaborator_event,
    publish_crawl_log,
    publish_edge,
    publish_node,
    publish_timeline_event,
    save_session,
    set_streaming_url,
    upsert_canonical_paper,
)
from .schemas import (
    AgentState,
    AgentStatus,
    CanonicalPaper,
    CrawlLogEntry,
    Entity,
    LogLevel,
    Relationship,
    SessionCollaboratorEvent,
    SessionStatus,
    SourceRef,
    TimelineEvent,
    TimelineEventType,
    utcnow_iso,
)

log = logging.getLogger(__name__)


# --- Structured-output schema (the TinyFish feature-gated output_schema field) ---
#
# Constraints enforced by TinyFish validator (see docs):
#   - No `oneOf` (use `anyOf`)
#   - No `type: [x, null]` (use `nullable: true`)
#   - No `additionalProperties`, `const`
#   - Max depth 10, max size 64KB
NEXUS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "papers": {
            "type": "array",
            "maxItems": 30,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "authors": {
                        "type": "array",
                        "maxItems": 10,
                        "items": {"type": "string"},
                    },
                    "year": {"type": "integer", "nullable": True},
                    "venue": {"type": "string", "nullable": True},
                    "doi": {"type": "string", "nullable": True},
                    "arxivId": {"type": "string", "nullable": True},
                    "abstract": {"type": "string", "nullable": True},
                    "methodology": {"type": "string", "nullable": True},
                    "keyFindings": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
                    "references": {"type": "array", "maxItems": 10, "items": {"type": "string"}},
                    "citedBy": {"type": "array", "maxItems": 10, "items": {"type": "string"}},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["title"],
            },
        },
        "textExcerpt": {"type": "string", "nullable": True},
        "outboundLinks": {
            "type": "array",
            "maxItems": 10,
            "items": {"type": "string"},
        },
    },
    "required": ["papers"],
}


def _build_goal(topic: str) -> str:
    """Natural-language goal for the Agent. Structured output is enforced by `output_schema`."""
    return (
        f"You are researching the topic: '{topic}'. "
        "Search broadly across the public web, including niche and non-mainstream sources. "
        "Extract papers, reports, posts, and relevant entities as structured records. "
        "For each paper return: title, authors, year, venue, doi or arxivId, abstract, "
        "methodology summary, and key findings. "
        "Citation Chain Traversal: when a paper is found, include up to 5 references and up to 5 "
        "cited-by papers to expand the graph naturally. "
        "Also return textExcerpt and outboundLinks for evidence and next-hop crawling. "
        "Return JSON matching the provided schema."
    )


# --- Live runner ---


def _event_type(event: Any) -> str:
    """Extract the event.type string from a tinyfish SDK event.

    The SDK emits typed dataclass objects with a `type` field whose value
    is either a plain string ("STARTED", "STREAMING_URL", etc.) or an
    EventType enum. This helper normalises both forms into an uppercase string.
    """
    t = getattr(event, "type", None)
    if t is None:
        return ""
    # If it's an Enum, `.value` is the canonical string; else fall through to str(t).
    value = getattr(t, "value", t)
    return str(value).upper()


async def run_live_agent(
    session_id: str, topic: str, seed_url: str
) -> None:  # pragma: no cover - network
    """Stream a real TinyFish run and relay events to Redis.

    We dispatch on `event.type` strings (STARTED / STREAMING_URL / PROGRESS /
    HEARTBEAT / COMPLETE as documented at
    https://docs.tinyfish.ai/agent-api/reference) rather than isinstance,
    so this code is stable across TinyFish SDK minor version bumps.
    """
    # Imported lazily so MOCK_TINYFISH=1 users don't need tinyfish pkg at import time.
    from tinyfish import AsyncTinyFish  # type: ignore[import-not-found]

    settings = get_settings()
    client = AsyncTinyFish(api_key=settings.tinyfish_api_key or None)

    seq = 0
    pages_visited = 0
    topic_node_id = entity_id("concept", f"topic:{topic}")
    topic_node_emitted = False

    await publish_agent_status(
        session_id,
        AgentStatus(
            sessionId=session_id,
            state=AgentState.browsing,
            currentUrl=seed_url,
            pagesVisited=0,
            queueLength=1,
            lastAction="Starting TinyFish Agent",
        ),
    )
    seq += 1
    await publish_timeline_event(
        session_id,
        TimelineEvent(
            sessionId=session_id,
            sequenceNumber=seq,
            type=TimelineEventType.query_started,
            label=f"Research started: {topic}",
            url=seed_url,
        ),
    )

    goal = _build_goal(topic)
    try:
        try:
            stream_ctx = client.agent.stream(
                url=seed_url, goal=goal, output_schema=NEXUS_OUTPUT_SCHEMA
            )
        except TypeError:
            # Backward compatibility for SDK versions that don't support output_schema.
            stream_ctx = client.agent.stream(url=seed_url, goal=goal)
        async with stream_ctx as stream:
            async for event in stream:
                ev_type = _event_type(event)

                if ev_type == "STARTED":
                    session = await load_session(session_id)
                    if session is not None:
                        session.runId = getattr(event, "run_id", None) or getattr(
                            event, "runId", None
                        )
                        await save_session(session)

                elif ev_type == "STREAMING_URL":
                    url = getattr(event, "streaming_url", None) or getattr(
                        event, "streamingUrl", None
                    )
                    if url:
                        await set_streaming_url(session_id, url)
                        session = await load_session(session_id)
                        if session is not None:
                            session.streamingUrl = url
                            await save_session(session)
                        await publish_agent_status(
                            session_id,
                            AgentStatus(
                                sessionId=session_id,
                                state=AgentState.browsing,
                                currentUrl=seed_url,
                                streamingUrl=url,
                                pagesVisited=pages_visited,
                                lastAction="Live browser preview ready",
                            ),
                        )

                elif ev_type == "PROGRESS":
                    pages_visited += 1
                    purpose = getattr(event, "purpose", None) or "Agent thinking..."
                    current_url = getattr(event, "url", None) or seed_url
                    # Emit a lightweight live graph trail while crawl is in progress.
                    if not topic_node_emitted:
                        await publish_node(
                            session_id,
                            Entity(
                                id=topic_node_id,
                                name=topic,
                                type="concept",
                                claims=["Live crawl root topic"],
                                confidence=1.0,
                                sources=[SourceRef(url=seed_url, title=seed_url)],
                            ),
                        )
                        topic_node_emitted = True
                    page_node_id = entity_id("concept", f"page:{current_url}")
                    await publish_node(
                        session_id,
                        Entity(
                            id=page_node_id,
                            name=_page_label(current_url),
                            type="concept",
                            claims=[purpose[:120]],
                            confidence=0.55,
                            sources=[SourceRef(url=current_url, title=current_url)],
                        ),
                    )
                    await publish_edge(
                        session_id,
                        Relationship(
                            id=relationship_id(topic_node_id, page_node_id, "visited"),
                            fromId=topic_node_id,
                            toId=page_node_id,
                            predicate="visited",
                            confidence=0.6,
                            sources=[SourceRef(url=current_url, title=current_url)],
                        ),
                    )
                    seq += 1
                    await publish_timeline_event(
                        session_id,
                        TimelineEvent(
                            sessionId=session_id,
                            sequenceNumber=seq,
                            type=TimelineEventType.page_visited,
                            label=purpose[:80],
                            url=current_url,
                        ),
                    )
                    await publish_crawl_log(
                        session_id,
                        CrawlLogEntry(
                            sessionId=session_id, level=LogLevel.info, message=purpose
                        ),
                    )
                    await publish_agent_status(
                        session_id,
                        AgentStatus(
                            sessionId=session_id,
                            state=AgentState.extracting,
                            currentUrl=seed_url,
                            pagesVisited=pages_visited,
                            lastAction=purpose[:80],
                        ),
                    )

                elif ev_type == "COMPLETE":
                    result = getattr(event, "result", None) or getattr(
                        event, "result_json", None
                    )
                    status_ok = (
                        str(getattr(event, "status", "COMPLETED")).upper() == "COMPLETED"
                    )
                    if result and status_ok:
                        # Redis-native path: enqueue raw extraction for normalizer worker.
                        await enqueue_raw_extraction(session_id, seed_url, result)
                        # Fallback ingest for single-process local dev when worker isn't running.
                        if not settings.redis_native_pipeline:
                            await _ingest_raw_locally(session_id, seed_url, result, seq)
                    await publish_agent_status(
                        session_id,
                        AgentStatus(
                            sessionId=session_id,
                            state=AgentState.done if status_ok else AgentState.error,
                            currentUrl=seed_url,
                            pagesVisited=pages_visited,
                            lastAction="Agent complete" if status_ok else "Agent failed",
                        ),
                    )
                    seq += 1
                    await publish_timeline_event(
                        session_id,
                        TimelineEvent(
                            sessionId=session_id,
                            sequenceNumber=seq,
                            type=(
                                TimelineEventType.fact_extracted
                                if status_ok
                                else TimelineEventType.agent_error
                            ),
                            label="Agent run finished",
                        ),
                    )
                    break
                # HEARTBEAT and any unknown event types are ignored on purpose.

    except Exception as exc:
        log.exception("Live agent run failed for session %s", session_id)
        await publish_crawl_log(
            session_id,
            CrawlLogEntry(
                sessionId=session_id, level=LogLevel.error, message=f"Agent error: {exc}"
            ),
        )
        await publish_agent_status(
            session_id,
            AgentStatus(
                sessionId=session_id,
                state=AgentState.error,
                lastAction=str(exc)[:120],
            ),
        )
    finally:
        session = await load_session(session_id)
        if session is not None and session.status != SessionStatus.paused:
            session.status = SessionStatus.complete
            await save_session(session)


# --- Local ingest helper (used by worker and single-process fallback) ---


async def ingest_normalized_record(
    session_id: str,
    kind: str,
    payload: dict[str, Any],
    *,
    source_url: str | None = None,
    source_title: str | None = None,
) -> None:
    """Publish a single normalized entity or relationship to Redis.
    """
    source_refs: list[SourceRef] = []
    if source_url:
        source_refs.append(
            SourceRef(url=source_url, title=source_title or source_url)
        )

    if kind == "entity":
        if payload.get("type") == "paper":
            paper_payload = payload.get("paper") if isinstance(payload.get("paper"), dict) else payload
            paper = normalize_paper_record(paper_payload, source_url=source_url)
            merged = await upsert_canonical_paper(session_id, paper)
            payload = {
                "id": merged.paperId,
                "name": merged.title,
                "type": "paper",
                "claims": paper_to_entity_claims(merged),
                "aliases": [merged.doi, merged.arxivId] if merged.doi or merged.arxivId else [],
                "sources": payload.get("sources", []),
                "confidence": merged.confidence,
            }
        entity = Entity(
            id=payload.get("id") or entity_id(payload["type"], payload["name"]),
            name=payload["name"],
            type=payload["type"],
            aliases=payload.get("aliases", []),
            claims=payload.get("claims", []),
            sources=source_refs if not payload.get("sources") else payload["sources"],
            confidence=float(payload.get("confidence", 0.7)),
            firstSeen=payload.get("firstSeen", utcnow_iso()),
        )
        await publish_node(session_id, entity)

    elif kind == "relationship":
        # Accept both contract styles:
        # 1) canonical ids: fromId/toId
        # 2) readable names: fromName/toName (+ optional fromType/toType)
        from_id = payload.get("fromId")
        to_id = payload.get("toId")
        if not from_id and payload.get("fromName"):
            from_type = payload.get("fromType", "paper")
            from_id = entity_id(from_type, payload["fromName"])
        if not to_id and payload.get("toName"):
            to_type = payload.get("toType", "paper")
            to_id = entity_id(to_type, payload["toName"])
        predicate = payload.get("predicate")
        if not from_id or not to_id or not predicate:
            log.warning("Skipping malformed relationship payload for %s: %s", session_id, payload)
            return
        rel = Relationship(
            id=payload.get("id")
            or relationship_id(from_id, to_id, predicate),
            fromId=from_id,
            toId=to_id,
            predicate=predicate,
            confidence=float(payload.get("confidence", 0.7)),
            sources=source_refs if not payload.get("sources") else payload["sources"],
        )
        await publish_edge(session_id, rel)


async def _ingest_raw_locally(
    session_id: str, source_url: str, raw_result: dict[str, Any], seq_start: int
) -> None:
    """Local normalization path for worker processing and fallback execution.

    Keeps the demo runnable in single-process mode if the worker is disabled.
    """
    papers = raw_result.get("papers", []) or raw_result.get("entities", []) or []
    source_title = raw_result.get("textExcerpt", source_url)[:80]
    seq = seq_start

    name_to_id: dict[str, str] = {}
    paper_nodes: list[CanonicalPaper] = []

    for item in papers:
        title = item.get("title") or item.get("name")
        if not title:
            continue
        new_url = await mark_url_visited(session_id, source_url)
        if not new_url:
            # Not a reason to skip the entity itself, just log it.
            pass
        paper = normalize_paper_record(item, source_url=source_url)
        paper = await upsert_canonical_paper(session_id, paper)
        paper_nodes.append(paper)
        eid = paper.paperId
        name_to_id[paper.title] = eid
        entity = Entity(
            id=eid,
            name=paper.title,
            type="paper",
            claims=paper_to_entity_claims(paper),
            aliases=[x for x in [paper.doi, paper.arxivId] if x],
            confidence=float(item.get("confidence", paper.confidence)),
            sources=[SourceRef(url=source_url, title=source_title)],
        )
        await publish_node(session_id, entity)
        seq += 1
        await publish_timeline_event(
            session_id,
            TimelineEvent(
                sessionId=session_id,
                sequenceNumber=seq,
                type=TimelineEventType.entity_normalized,
                label=f"Extracted paper: {paper.title[:60]}",
                entityId=eid,
                url=source_url,
            ),
        )
        await asyncio.sleep(0.15)

    branch_limit = max(get_settings().citation_branch_limit, 1)
    for paper in paper_nodes:
        src_name = paper.title
        if src_name not in name_to_id:
            continue
        neighbors = [("references", x) for x in paper.references[:branch_limit]] + [
            ("cited_by", x) for x in paper.citedBy[:branch_limit]
        ]
        for pred, dst_name in neighbors:
            dst_id = name_to_id.get(dst_name)
            if not dst_id:
                dst_id = entity_id("paper", dst_name)
                name_to_id[dst_name] = dst_id
                auto_entity = Entity(
                    id=dst_id,
                    name=dst_name,
                    type="paper",
                    claims=[],
                    sources=[SourceRef(url=source_url, title=source_title)],
                )
                await publish_node(session_id, auto_entity)

            rid = relationship_id(name_to_id[src_name], dst_id, pred)
            await publish_edge(
                session_id,
                Relationship(
                    id=rid,
                    fromId=name_to_id[src_name],
                    toId=dst_id,
                    predicate=pred,
                    sources=[SourceRef(url=source_url, title=source_title)],
                ),
            )
            seq += 1
            await publish_timeline_event(
                session_id,
                TimelineEvent(
                    sessionId=session_id,
                    sequenceNumber=seq,
                    type=TimelineEventType.edge_created,
                    label=f"{src_name} -> {pred} -> {dst_name}",
                    relationshipId=rid,
                ),
            )
            await asyncio.sleep(0.1)


# --- Entry point used by the REST route ---


async def run_agent_for_session(session_id: str, topic: str, seed_url: str) -> None:
    """Top-level agent runner. Picks mock vs live based on settings."""
    settings = get_settings()
    await mark_url_visited(session_id, seed_url)
    await publish_collaborator_event(
        session_id,
        SessionCollaboratorEvent(
            sessionId=session_id,
            collaborator="system",
            action="session_started",
        ),
    )

    if settings.mock_tinyfish or not settings.tinyfish_api_key:
        reason = "MOCK_TINYFISH=1" if settings.mock_tinyfish else "no TINYFISH_API_KEY"
        log.info("Starting MOCK agent run for session %s (%s)", session_id, reason)
        await publish_crawl_log(
            session_id,
            CrawlLogEntry(
                sessionId=session_id,
                level=LogLevel.info,
                message=f"Mock mode active ({reason})",
            ),
        )
        await run_mock_agent(session_id, topic, seed_url)
    else:
        log.info("Starting LIVE agent run for session %s", session_id)
        await run_live_agent(session_id, topic, seed_url)


# Small helper so main.py can jitter the initial agent status without blocking.
async def sleep_jitter(base: float, spread: float = 0.4) -> None:
    await asyncio.sleep(base + random.random() * spread)


def _page_label(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.netloc or url
        path = parsed.path.strip("/")
        if path:
            return f"{host}/{path[:60]}"
        return host
    except Exception:
        return url[:80]
