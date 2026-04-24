# Nexus Sponsor Usage (Simple + Detailed)

This document explains what we use from each sponsor, how each feature helps, and how all parts connect in runtime.

---

## What Nexus does

Nexus runs a live research workflow:

1. an agent browses and extracts research data,
2. backend normalizes and stores it,
3. UI receives live updates and generates researcher-friendly output.

---

## 1) TinyFish — Agent runtime and extraction

### Features we use

- TinyFish SDK client (`AsyncTinyFish`) in `backend/app/tinyfish_runner.py`
- event-stream run loop (`client.agent.stream(...)`)
- stream events:
  - started/status updates
  - `STREAMING_URL` for live preview
  - progress actions
  - completion payload
- schema-guided extraction (`NEXUS_OUTPUT_SCHEMA`)
- live/mock switching (`run_agent_for_session(...)`)
- mock fallback in `backend/app/mock_stream.py`

### What this helps with

- avoids custom scraper logic per website
- gives transparent live browser behavior for trust
- produces structured payloads that can be normalized and used in graph/report generation

### Where this is visible

- left live preview panel and expanded modal
- activity logs
- final extracted data entering Redis stream pipeline

---

## 2) Redis — Realtime, pipeline, memory, search, caching

Redis is the core backend backbone in this project.

### A) Realtime event fanout (Pub/Sub)

Channels used:

- `nexus:events:{sessionId}:node`
- `nexus:events:{sessionId}:edge`
- `nexus:events:{sessionId}:agent`
- `nexus:events:{sessionId}:log`
- `nexus:events:{sessionId}:timeline`
- `nexus:events:{sessionId}:collaborator`

Code: `backend/app/redis_client.py` publish helpers.

### B) Durable processing (Streams + consumer groups)

- raw stream: `nexus:stream:raw_extract`
- dead-letter stream: `nexus:stream:dlq`
- consumer group processing in normalizer worker

Code:

- stream enqueue/read/ack in `backend/app/redis_client.py`
- processing loop in `backend/app/workers/normalizer.py`

### C) Dedup and memory

- URL dedupe: Bloom (`BF.ADD`) with set fallback
- session storage, timeline replay, canonical paper mappings

Code: `backend/app/redis_client.py`

### D) Semantic search (Redis Search + vectors)

- vector index creation (`FT.CREATE`, HNSW)
- vector query (`FT.SEARCH` KNN by session)
- fallback keyword search when vector path fails

Code: `backend/app/context_engine.py` + fallback in `backend/app/redis_client.py`

### E) Redis caching we use

1. **Embedding cache**  
   Avoids recomputing embeddings for same text/model.

2. **Context query cache**  
   Caches context query results per session/query/version.

Code: `backend/app/context_engine.py`, version bump in `backend/app/redis_client.py`

### Important runtime note

Cache improves repeated context lookup latency, but full same-topic runs can still take time because agent browsing/extraction itself still runs.

---

## 3) WunderGraph Cosmo — GraphQL realtime bridge

### Features we use

- Cosmo Router as GraphQL gateway for realtime subscriptions
- EDFS subscriptions connected to Redis channels
- `@edfs__redisSubscribe` in router subgraph schema
- router compose flow (`wgc router compose`)
- frontend SSE subscriptions (`graphql-sse` + `urql`)

### Config and code

- router schema/config:
  - `router/subgraphs/research.graphql`
  - `router/subgraphs/base.graphql`
  - `router/router-config.yaml`
  - `router/config.json`
- frontend subscription wiring:
  - `frontend/src/api/graphqlClient.ts`
  - `frontend/src/api/subscriptions.ts`
  - `frontend/src/hooks/useSessionSubscriptions.ts`

### What this helps with

- stable realtime sync without custom websocket service
- same session updates delivered to all connected clients

### Honest boundary

We are using Cosmo strongly for realtime subscriptions.
We are not yet using deeper hook/policy workflows in advanced depth.

---

## 4) Infra and security hardening used

- Chainguard-based worker image: `backend/Dockerfile.worker`
- pinned image digests in `docker-compose.yml`
- non-root worker runtime with dropped privileges
- container security workflow:
  - `.github/workflows/container-security.yml`
  - Trivy scans

---

## 5) End-to-end flow (all sponsors together)

1. Frontend starts session (`POST /sessions`).
2. TinyFish run starts and emits progress/completion events.
3. Backend publishes realtime events to Redis Pub/Sub.
4. Backend enqueues extraction payloads to Redis Streams.
5. Normalizer consumes stream, builds entities/relations, publishes updates.
6. Cosmo relays Redis-backed events via GraphQL subscriptions.
7. Frontend store updates graph, panels, logs, and report inputs.
8. Final report generation uses extracted findings + sources (+ semantic context when available).

---

## 6) Quick verification checklist

### TinyFish

- live preview URL appears
- progress logs stream
- completion payload is enqueued

### Redis

- `docker compose exec -T redis redis-cli PUBSUB CHANNELS "nexus:events:*"`
- `docker compose exec -T redis redis-cli XLEN nexus:stream:raw_extract`
- `docker compose exec -T redis redis-cli XINFO GROUPS nexus:stream:raw_extract`
- `docker compose exec -T redis redis-cli FT._LIST`
- `docker compose exec -T redis redis-cli KEYS "nexus:context:vec:*"`

### WunderGraph

- `cd router && npm run compose`
- frontend receives:
  - `nodeAdded`
  - `edgeLinked`
  - `agentStatusChanged`
  - `crawlLog`
  - `collaboratorEvent`

