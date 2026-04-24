"""Redis client + all the pub/sub and dedup helpers.

Channel conventions (must match `router/subgraphs/research.graphql`):

    nexus:events:{sessionId}:node       -> NodeAddedEvent
    nexus:events:{sessionId}:edge       -> EdgeLinkedEvent
    nexus:events:{sessionId}:agent      -> AgentStatusChangedEvent
    nexus:events:{sessionId}:log        -> CrawlLogEntry
    nexus:events:{sessionId}:timeline   -> TimelineEvent

Every JSON payload MUST include a `__typename` field or the Cosmo Router
will discard the message (this is an EDFS requirement for Union/Interface
type resolution).

Other keys used:
    nexus:visited:{sessionId}           -> RedisBloom BF.ADD (URL dedup)
    nexus:visited_set:{sessionId}       -> Redis SET fallback (when BF unavailable)
    nexus:session:{sessionId}           -> JSON blob for ResearchSession
    nexus:streaming_url:{sessionId}     -> str (TinyFish live preview URL)
    nexus:timeline:{sessionId}          -> ZSET (score = sequenceNumber, member = event JSON)
"""

from __future__ import annotations

import json
import logging
import base64
from typing import Any

import redis.asyncio as redis_async
from redis.asyncio import Redis

from .config import get_settings
from .schemas import (
    AgentStatus,
    CanonicalPaper,
    CrawlLogEntry,
    Entity,
    Relationship,
    ResearchSession,
    SessionCollaboratorEvent,
    TimelineEvent,
)

log = logging.getLogger(__name__)


_redis: Redis | None = None
_redis_binary: Redis | None = None


def get_redis() -> Redis:
    """Return a process-wide async Redis client.

    `decode_responses=True` keeps pub/sub payloads as str so we can
    `json.loads` directly; the Cosmo Router also expects UTF-8 JSON.
    """
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = redis_async.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


def get_redis_binary() -> Redis:
    """Binary-safe client for vector blobs and FT.SEARCH params."""
    global _redis_binary
    if _redis_binary is None:
        settings = get_settings()
        _redis_binary = redis_async.from_url(
            settings.redis_url,
            decode_responses=False,
        )
    return _redis_binary


async def close_redis() -> None:
    global _redis, _redis_binary
    if _redis is not None:
        await _redis.aclose()
        _redis = None
    if _redis_binary is not None:
        await _redis_binary.aclose()
        _redis_binary = None


# --- URL dedup (RedisBloom with SET fallback) ---

_BLOOM_AVAILABLE: bool | None = None


async def _bloom_available() -> bool:
    """Probe BF.RESERVE once per process; fall back to SET if unavailable."""
    global _BLOOM_AVAILABLE
    if _BLOOM_AVAILABLE is not None:
        return _BLOOM_AVAILABLE
    r = get_redis()
    try:
        await r.execute_command(
            "BF.RESERVE", "nexus:bf:probe", "0.001", "10000", "NONSCALING"
        )
        _BLOOM_AVAILABLE = True
    except Exception as exc:  # pragma: no cover - depends on Redis module load
        # BUSYKEY / ITEM EXISTS are both fine; other errors mean module not loaded.
        upper = str(exc).upper()
        if "BUSYKEY" in upper or "ITEM EXISTS" in upper:
            _BLOOM_AVAILABLE = True
        else:
            log.warning("RedisBloom unavailable (%s); falling back to SET for dedup", exc)
            _BLOOM_AVAILABLE = False
    return _BLOOM_AVAILABLE


async def mark_url_visited(session_id: str, url: str) -> bool:
    """Return True if the URL is new (should be crawled), False if already seen."""
    r = get_redis()
    if await _bloom_available():
        key = f"nexus:visited:{session_id}"
        added = await r.execute_command("BF.ADD", key, url)
        await r.expire(key, 3600)
        return int(added) == 1
    # Fallback: plain Redis SET
    key = f"nexus:visited_set:{session_id}"
    added = await r.sadd(key, url)
    await r.expire(key, 3600)
    return int(added) == 1


# --- Pub/sub publishers (each enforces __typename) ---


def _channel(session_id: str, suffix: str) -> str:
    return f"nexus:events:{session_id}:{suffix}"


async def _publish(channel: str, typename: str, payload: dict[str, Any]) -> None:
    # Strict EDFS mode allows only entity key fields in event-driven graphs.
    # We encode the payload into `id` so the frontend can decode it back.
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    encoded = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("ascii")
    body = {"__typename": typename, "id": f"{typename}:{encoded}"}
    await get_redis().publish(channel, json.dumps(body))


async def incr_session_diagnostic(session_id: str, field: str, amount: int = 1) -> None:
    await get_redis().hincrby(f"nexus:diag:{session_id}", field, amount)
    await get_redis().expire(f"nexus:diag:{session_id}", 24 * 3600)


async def get_session_diagnostics(session_id: str) -> dict[str, Any]:
    raw = await get_redis().hgetall(f"nexus:diag:{session_id}")
    out: dict[str, Any] = {}
    for k, v in raw.items():
        try:
            out[k] = int(v)
        except Exception:
            out[k] = v
    return out


async def publish_node(session_id: str, entity: Entity) -> None:
    ent = entity.model_dump(mode="json")
    ent["__typename"] = "Entity"
    # Nested SourceRefs also get __typename, just to be safe against future
    # schema changes that might make the field polymorphic.
    for src in ent.get("sources", []):
        src.setdefault("__typename", "SourceRef")
    await _publish(
        _channel(session_id, "node"),
        "NodeAddedEvent",
        {"sessionId": session_id, "entity": ent},
    )
    await incr_session_diagnostic(session_id, "nodes_emitted", 1)


async def publish_edge(session_id: str, relationship: Relationship) -> None:
    rel = relationship.model_dump(mode="json")
    rel["__typename"] = "Relationship"
    for src in rel.get("sources", []):
        src.setdefault("__typename", "SourceRef")
    await _publish(
        _channel(session_id, "edge"),
        "EdgeLinkedEvent",
        {"sessionId": session_id, "relationship": rel},
    )
    await incr_session_diagnostic(session_id, "edges_emitted", 1)


async def publish_agent_status(session_id: str, status: AgentStatus) -> None:
    stat = status.model_dump(mode="json")
    stat["__typename"] = "AgentStatus"
    await _publish(
        _channel(session_id, "agent"),
        "AgentStatusChangedEvent",
        {"sessionId": session_id, "status": stat},
    )


async def publish_crawl_log(session_id: str, entry: CrawlLogEntry) -> None:
    await _publish(
        _channel(session_id, "log"),
        "CrawlLogEntry",
        entry.model_dump(mode="json"),
    )
    await incr_session_diagnostic(session_id, "logs_emitted", 1)


async def publish_timeline_event(session_id: str, event: TimelineEvent) -> None:
    # Persist in a sorted set so the replay mode can query the full history.
    ev_json = event.model_dump(mode="json")
    await get_redis().zadd(
        f"nexus:timeline:{session_id}",
        {json.dumps(ev_json): event.sequenceNumber},
    )
    await _publish(_channel(session_id, "timeline"), "TimelineEvent", ev_json)


async def publish_collaborator_event(
    session_id: str, event: SessionCollaboratorEvent
) -> None:
    await _publish(
        _channel(session_id, "collaborator"),
        "SessionCollaboratorEvent",
        event.model_dump(mode="json"),
    )


# --- Redis Streams pipeline ---


async def ensure_stream_group(stream: str, group: str) -> None:
    r = get_redis()
    try:
        await r.xgroup_create(stream, group, id="0-0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc).upper():
            raise


async def enqueue_raw_extraction(
    session_id: str, source_url: str, payload: dict[str, Any]
) -> str:
    settings = get_settings()
    await ensure_stream_group(settings.redis_raw_stream, settings.redis_stream_group)
    record = {
        "sessionId": session_id,
        "sourceUrl": source_url,
        "payload": json.dumps(payload, separators=(",", ":")),
    }
    msg_id = await get_redis().xadd(settings.redis_raw_stream, record, maxlen=10000, approximate=True)
    await incr_session_diagnostic(session_id, "raw_extract_enqueued", 1)
    return msg_id


async def read_raw_batch(
    *,
    stream: str,
    group: str,
    consumer: str,
    count: int,
    block_ms: int,
) -> list[tuple[str, dict[str, str]]]:
    r = get_redis()
    try:
        data = await r.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=count,
            block=block_ms,
        )
    except Exception as exc:
        if "NOGROUP" in str(exc).upper():
            await ensure_stream_group(stream, group)
            return []
        raise
    out: list[tuple[str, dict[str, str]]] = []
    for _, messages in data:
        for msg_id, fields in messages:
            out.append((msg_id, fields))
    return out


async def ack_raw_message(stream: str, group: str, msg_id: str) -> None:
    await get_redis().xack(stream, group, msg_id)


async def move_to_dlq(dlq_stream: str, msg_id: str, reason: str, raw_fields: dict[str, str]) -> None:
    fields = {"failedId": msg_id, "reason": reason, **raw_fields}
    await get_redis().xadd(dlq_stream, fields, maxlen=5000, approximate=True)


# --- Session state (tiny KV; proper store would use Postgres) ---


async def save_session(session: ResearchSession) -> None:
    await get_redis().set(
        f"nexus:session:{session.id}",
        session.model_dump_json(),
        ex=24 * 3600,
    )


async def load_session(session_id: str) -> ResearchSession | None:
    raw = await get_redis().get(f"nexus:session:{session_id}")
    if not raw:
        return None
    return ResearchSession.model_validate_json(raw)


async def list_sessions() -> list[ResearchSession]:
    r = get_redis()
    keys: list[str] = []
    async for key in r.scan_iter(match="nexus:session:*"):
        keys.append(key)
    if not keys:
        return []
    raws = await r.mget(keys)
    return [
        ResearchSession.model_validate_json(raw)
        for raw in raws
        if raw is not None
    ]


# --- Streaming URL cache (TinyFish live browser preview) ---


async def set_streaming_url(session_id: str, url: str) -> None:
    await get_redis().set(f"nexus:streaming_url:{session_id}", url, ex=3600)


async def get_streaming_url(session_id: str) -> str | None:
    return await get_redis().get(f"nexus:streaming_url:{session_id}")


# --- Timeline replay query ---


async def read_timeline(
    session_id: str, start: int = 0, end: int = -1
) -> list[dict[str, Any]]:
    """Return TimelineEvent dicts in sequence order."""
    raw = await get_redis().zrange(
        f"nexus:timeline:{session_id}", start, end, withscores=False
    )
    return [json.loads(item) for item in raw]


# --- Cross-session canonical paper index ---


async def upsert_canonical_paper(session_id: str, paper: CanonicalPaper) -> CanonicalPaper:
    """Merge paper into global index + map membership into this session."""
    r = get_redis()
    pid = paper.paperId
    global_key = f"nexus:paper:{pid}"
    session_set = f"nexus:session:{session_id}:papers"
    global_sessions = f"nexus:paper:{pid}:sessions"

    existing_raw = await r.get(global_key)
    if existing_raw:
        existing = CanonicalPaper.model_validate_json(existing_raw)
        merged = CanonicalPaper(
            paperId=pid,
            title=paper.title if len(paper.title) >= len(existing.title) else existing.title,
            authors=sorted(set(existing.authors + paper.authors)),
            year=paper.year or existing.year,
            venue=paper.venue or existing.venue,
            doi=paper.doi or existing.doi,
            arxivId=paper.arxivId or existing.arxivId,
            citationCount=max(existing.citationCount or 0, paper.citationCount or 0) or None,
            abstract=paper.abstract or existing.abstract,
            methodology=paper.methodology or existing.methodology,
            keyFindings=sorted(set(existing.keyFindings + paper.keyFindings))[:12],
            references=sorted(set(existing.references + paper.references))[:25],
            citedBy=sorted(set(existing.citedBy + paper.citedBy))[:25],
            sourceUrl=paper.sourceUrl or existing.sourceUrl,
            confidence=max(existing.confidence, paper.confidence),
        )
    else:
        merged = paper

    await r.set(global_key, merged.model_dump_json(), ex=14 * 24 * 3600)
    await r.sadd(session_set, pid)
    await r.expire(session_set, 14 * 24 * 3600)
    await r.sadd(global_sessions, session_id)
    await r.expire(global_sessions, 14 * 24 * 3600)
    # Index document text for lightweight context retrieval.
    doc = json.dumps(
        {
            "paperId": merged.paperId,
            "sessionId": session_id,
            "title": merged.title,
            "authors": merged.authors,
            "year": merged.year,
            "venue": merged.venue,
            "abstract": merged.abstract,
            "methodology": merged.methodology,
            "keyFindings": merged.keyFindings,
            "references": merged.references,
            "citedBy": merged.citedBy,
        },
        ensure_ascii=False,
    )
    await r.hset("nexus:context:docs", merged.paperId, doc)
    await r.sadd(f"nexus:context:session:{session_id}", merged.paperId)
    await r.expire(f"nexus:context:session:{session_id}", 14 * 24 * 3600)
    # Bump per-session context version so cached context query results are invalidated.
    await r.incr(f"nexus:context:version:{session_id}")
    await r.expire(f"nexus:context:version:{session_id}", 14 * 24 * 3600)
    try:
        from .context_engine import index_context_document

        await index_context_document(session_id=session_id, paper_id=merged.paperId, document=doc)
    except Exception as exc:
        log.warning("Vector indexing skipped for %s: %s", merged.paperId, exc)
    return merged


async def read_session_papers(session_id: str) -> list[CanonicalPaper]:
    r = get_redis()
    ids = await r.smembers(f"nexus:session:{session_id}:papers")
    if not ids:
        return []
    raws = await r.mget([f"nexus:paper:{pid}" for pid in ids])
    out: list[CanonicalPaper] = []
    for raw in raws:
        if raw:
            out.append(CanonicalPaper.model_validate_json(raw))
    return out


async def search_context(session_id: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    r = get_redis()
    ids = await r.smembers(f"nexus:context:session:{session_id}")
    if not ids:
        return []
    docs_raw = await r.hmget("nexus:context:docs", list(ids))
    scored: list[tuple[int, dict[str, Any]]] = []
    q = query.lower().strip()
    for item in docs_raw:
        if not item:
            continue
        doc = json.loads(item)
        hay = " ".join(
            [
                doc.get("title", ""),
                doc.get("abstract", "") or "",
                doc.get("methodology", "") or "",
                " ".join(doc.get("keyFindings", []) or []),
            ]
        ).lower()
        score = hay.count(q) if q else 0
        if score > 0 or not q:
            scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]
