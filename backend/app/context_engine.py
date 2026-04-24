"""Context retrieval with Redis Search vector index + fallback search."""

from __future__ import annotations

import array
import hashlib
import json
import logging
from typing import Any

import httpx

from .config import get_settings
from .redis_client import get_redis, get_redis_binary, incr_session_diagnostic, search_context

log = logging.getLogger(__name__)

_index_ready = False


def _vector_key(session_id: str, paper_id: str) -> str:
    return f"nexus:context:vec:{session_id}:{paper_id}"


def _vector_bytes(vector: list[float]) -> bytes:
    arr = array.array("f", vector)
    return arr.tobytes()


def _embedding_cache_key(model: str, text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"nexus:embed:cache:{model}:{digest}"


def _query_cache_key(session_id: str, context_version: str, top_k: int, query: str) -> str:
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
    return f"nexus:context:cache:{session_id}:{context_version}:{top_k}:{digest}"


async def _ensure_vector_index() -> None:
    global _index_ready
    if _index_ready:
        return
    settings = get_settings()
    r = get_redis_binary()
    try:
        await r.execute_command(
            "FT.CREATE",
            settings.redis_vector_index_name,
            "ON",
            "HASH",
            "PREFIX",
            "1",
            "nexus:context:vec:",
            "SCHEMA",
            "sessionId",
            "TAG",
            "paperId",
            "TAG",
            "title",
            "TEXT",
            "content",
            "TEXT",
            "embedding",
            "VECTOR",
            "HNSW",
            "6",
            "TYPE",
            "FLOAT32",
            "DIM",
            str(settings.embedding_dimension),
            "DISTANCE_METRIC",
            "COSINE",
        )
    except Exception as exc:
        if "INDEX ALREADY EXISTS" not in str(exc).upper():
            raise
    _index_ready = True


async def _embed_text(text: str) -> list[float]:
    settings = get_settings()
    if not settings.embedding_api_key:
        raise RuntimeError("EMBEDDING_API_KEY is not configured")
    normalized_text = " ".join(text.split())
    cache_ttl = max(0, settings.redis_embedding_cache_ttl_seconds)
    if cache_ttl > 0:
        key = _embedding_cache_key(settings.embedding_model, normalized_text)
        cached = await get_redis().get(key)
        if cached:
            try:
                parsed = json.loads(cached)
                if isinstance(parsed, list):
                    return [float(v) for v in parsed]
            except Exception:
                pass
    url = f"{settings.embedding_api_base.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.embedding_api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": settings.embedding_model, "input": normalized_text}
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()
    data = body.get("data") or []
    if not data:
        raise RuntimeError("Embedding response missing vector data")
    embedding = data[0].get("embedding")
    if not isinstance(embedding, list):
        raise RuntimeError("Embedding vector is invalid")
    vector = [float(v) for v in embedding]
    if cache_ttl > 0:
        await get_redis().set(key, json.dumps(vector, separators=(",", ":")), ex=cache_ttl)
    return vector


async def index_context_document(*, session_id: str, paper_id: str, document: str) -> None:
    settings = get_settings()
    if not settings.redis_vector_enabled:
        return
    await _ensure_vector_index()
    parsed = json.loads(document)
    content = " ".join(
        [
            parsed.get("title", "") or "",
            parsed.get("abstract", "") or "",
            parsed.get("methodology", "") or "",
            " ".join(parsed.get("keyFindings", []) or []),
        ]
    ).strip()
    if not content:
        return
    vector = await _embed_text(content)
    if len(vector) != settings.embedding_dimension:
        raise RuntimeError(
            f"Embedding dimension mismatch. expected={settings.embedding_dimension}, got={len(vector)}"
        )
    key = _vector_key(session_id, paper_id)
    await get_redis_binary().hset(
        key,
        mapping={
            "sessionId": session_id,
            "paperId": paper_id,
            "title": parsed.get("title", "") or "",
            "content": content,
            "embedding": _vector_bytes(vector),
        },
    )


async def query_session_context(session_id: str, query: str) -> list[dict]:
    settings = get_settings()
    normalized_query = " ".join(query.lower().split())
    context_version = await get_redis().get(f"nexus:context:version:{session_id}") or "0"
    cache_key = _query_cache_key(
        session_id=session_id,
        context_version=str(context_version),
        top_k=settings.redis_context_top_k,
        query=normalized_query,
    )
    cache_ttl = max(0, settings.redis_context_cache_ttl_seconds)
    if cache_ttl > 0:
        cached = await get_redis().get(cache_key)
        if cached:
            try:
                parsed = json.loads(cached)
                if isinstance(parsed, list):
                    await incr_session_diagnostic(session_id, "context_cache_hits", 1)
                    return parsed
            except Exception:
                pass
    await incr_session_diagnostic(session_id, "context_cache_misses", 1)

    results: list[dict] | None = None
    if settings.redis_vector_enabled:
        try:
            await _ensure_vector_index()
            query_vec = await _embed_text(normalized_query)
            if len(query_vec) == settings.embedding_dimension:
                q = (
                    f"(@sessionId:{{{session_id}}})=>"
                    f"[KNN {settings.redis_context_top_k} @embedding $vec AS score]"
                )
                raw = await get_redis_binary().execute_command(
                    "FT.SEARCH",
                    settings.redis_vector_index_name,
                    q,
                    "PARAMS",
                    "2",
                    "vec",
                    _vector_bytes(query_vec),
                    "SORTBY",
                    "score",
                    "RETURN",
                    "4",
                    "paperId",
                    "title",
                    "content",
                    "score",
                    "DIALECT",
                    "2",
                )
                results = _parse_vector_search(raw)
                await incr_session_diagnostic(session_id, "context_vector_hits", 1)
        except Exception as exc:
            log.warning("Vector search fallback activated: %s", exc)
    if results is None:
        results = await search_context(
            session_id, normalized_query, top_k=settings.redis_context_top_k
        )
        await incr_session_diagnostic(session_id, "context_fallback_hits", 1)
    if cache_ttl > 0:
        await get_redis().set(
            cache_key,
            json.dumps(results, separators=(",", ":"), ensure_ascii=False),
            ex=cache_ttl,
        )
    return results


async def related_session_context(session_id: str) -> list[dict]:
    settings = get_settings()
    if settings.redis_vector_enabled:
        # Query with neutral phrase to get broad nearest context.
        return await query_session_context(session_id, "highly relevant research context")
    return await search_context(session_id, "", top_k=settings.redis_context_top_k)


def _parse_vector_search(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        return []
    out: list[dict[str, Any]] = []
    for row in raw[1:]:
        if not isinstance(row, list) or len(row) < 2:
            continue
        fields = row[1]
        if not isinstance(fields, list):
            continue
        mapped: dict[str, Any] = {}
        for i in range(0, len(fields), 2):
            key = fields[i]
            value = fields[i + 1] if i + 1 < len(fields) else b""
            k = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            v = value.decode("utf-8", errors="ignore") if isinstance(value, bytes) else value
            mapped[k] = v
        out.append(mapped)
    return out
