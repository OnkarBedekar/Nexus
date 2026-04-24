# Nexus

> Live knowledge-graph research cockpit for the "Ship to Prod - Agentic Engineering" hackathon, San Francisco.

A user types a topic. A **TinyFish** web agent autonomously browses the live web while a React UI renders a D3 force-directed graph that assembles itself node-by-node in real time. **Redis** is the spine: durable extraction pipeline, semantic context, session memory, and realtime fanout. **WunderGraph Cosmo** turns those Redis-backed events into GraphQL subscriptions so every connected client stays in sync without a custom WebSocket service.

---

## Sponsors: what we use and what is unique

Below is how each sponsor product shows up in Nexus—not a generic integration list, but the **specific capabilities** we leaned on.

### TinyFish — agent runtime and structured extraction

| How we use it | Where |
| --- | --- |
| **`AsyncTinyFish`** client and **`agent.stream(...)`** event loop | `backend/app/tinyfish_runner.py` |
| **Live preview** from stream events (`STREAMING_URL` / streaming URL payload) | Left panel + expanded modal in the UI |
| **Schema-guided extraction** (`output_schema` / `NEXUS_OUTPUT_SCHEMA`) so the agent returns normalized paper/entity shapes | Same runner + schema constants |
| **Mock / live switch** for full-stack demos without API spend | `run_agent_for_session(...)`, `backend/app/mock_stream.py` |

**What is unique here**

- We avoid one-off scrapers per site: the agent handles navigation and extraction behind one contract (stream + schema).
- **One streaming URL per run** drives the iframe preview (not a screenshot API per page); the UI treats that as the “live trust surface” for the booth.
- **Two-phase live** (when configured): discovery pass (`discover_web_urls` in `backend/app/discovery.py`) prepends the user seed and dedupes URLs before extraction—so the graph starts from the chosen page first, then expands.
- **`output_schema`** is authored as a JSON Schema **subset** TinyFish accepts (no `oneOf`, no `additionalProperties`, no `const`; use `anyOf` and `nullable: true`). See “Notable deviations” below.

**Research angle**

- Academic-mode flags bias toward arXiv, Semantic Scholar, PubMed, Scholar, lab pages; bounded citation traversal (references + cited-by) feeds the graph without unbounded crawl.

---

### Redis — streams, pub/sub, Bloom, search/vectors, and caching

We use **Redis Stack** in Docker (`redis/redis-stack` in `docker-compose.yml`) so Bloom and RediSearch/vector features are available beside vanilla commands.

| Capability | How Nexus uses it | Code / keys |
| --- | --- | --- |
| **Pub/Sub fanout** | Per-session channels for nodes, edges, agent status, crawl logs, timeline, collaborators | `nexus:events:{sessionId}:*` — `backend/app/redis_client.py` |
| **Streams + consumer groups** | Raw extraction enqueued from the agent path; normalizer worker consumes with acks; DLQ stream for failures | `nexus:stream:raw_extract`, `nexus:stream:dlq` — `redis_client.py`, `backend/app/workers/normalizer.py` |
| **Bloom dedupe** | URL visit dedupe with **`BF.ADD`**; automatic **set fallback** if Bloom module is unavailable | `nexus:visited:{sessionId}` — see comments in `redis_client.py` |
| **RediSearch + vectors** | `FT.CREATE` with **HNSW**; **KNN** `FT.SEARCH` scoped by session for semantic context over canonical docs | `backend/app/context_engine.py` + fallbacks in `redis_client.py` |
| **Caching** | Embedding cache + context-query cache (versioned) to avoid recomputing hot paths | `context_engine.py`, version bump logic in `redis_client.py` |

**What is unique here**

- **Single product** carries: realtime UI events, **durable** pipeline (streams), **probabilistic** dedupe (Bloom), **vector** retrieval, and **HTTP-friendly** replay (timeline / session keys)—so Cosmo and FastAPI both read the same backbone.
- **Honest performance note**: caches speed repeated context lookups; a full new topic run still waits on real agent browsing unless mock mode is on.

Operator-level verification commands live in [SPONSOR_USAGE_DETAILED.md](SPONSOR_USAGE_DETAILED.md) (Pub/Sub channels, `XLEN`, consumer groups, `FT._LIST`, vector key patterns).

---

### WunderGraph Cosmo — GraphQL realtime without a subscription microservice

| How we use it | Where |
| --- | --- |
| **Cosmo Router** as the GraphQL gateway | Docker service `cosmo-router` in `docker-compose.yml` |
| **EDFS**: Redis-backed subscriptions via **`@edfs__redisSubscribe`** | `router/subgraphs/research.graphql` (and related base schema) |
| **Composition** | `wgc router compose` — `cd router && npm run compose` |
| **Frontend SSE** | `graphql-sse` + **urql** with `Accept: text/event-stream` | `frontend/src/api/graphqlClient.ts`, `subscriptions.ts`, `useSessionSubscriptions.ts` |

**What is unique here**

- Subscriptions are **declarative in GraphQL schema**: the Router subscribes to Redis channels directly—**no Node subscription server** in the hot path.
- Same session updates (e.g. `nodeAdded`, `edgeLinked`, `agentStatusChanged`, `crawlLog`, `collaboratorEvent`) reach **all** browsers subscribed through one gateway.

**Boundary**

- We use Cosmo **strongly for realtime subscriptions** (EDFS over Redis). We are not yet exercising deeper Cosmo policy/hook workflows end-to-end.

---

### Supply-chain and runtime hardening (images we depend on)

| Piece | What we did |
| --- | --- |
| **Pinned digests** | `redis/redis-stack` and `ghcr.io/wundergraph/cosmo/router` use immutable image SHA references in `docker-compose.yml` |
| **Chainguard-style worker** | Normalizer worker built from `backend/Dockerfile.worker` (`nexus-normalizer-worker:chainguard`), runs **non-root**, **read-only** rootfs, **dropped caps**, **`no-new-privileges`**, tmpfs for `/tmp` |
| **CI** | Container scanning (e.g. Trivy) in `.github/workflows/container-security.yml` |

---

## End-to-end sponsor flow (one paragraph)

`POST /sessions` starts a session → **TinyFish** streams browsing + completion → FastAPI **publishes** to Redis Pub/Sub and **XADD**s raw payloads to a Redis **Stream** → the **normalizer worker** reads the group, builds entities/edges, updates canonical store (and **vectors** when enabled) → more **PUBLISH** events → **Cosmo** maps Redis channels to GraphQL subscriptions → the React app updates the **D3** graph, panels, logs, and final-report inputs in lockstep.

---

## PhD research positioning

Nexus targets research pain points that typical literature tools handle poorly:

- citation rabbit holes that lose context
- static citation graphs that do not keep discovering live
- no continuity across sessions
- manual synthesis across related papers
- advisor meetings that need a narrative, not a raw paper list

### New API capabilities (implemented)

- `POST /sessions` accepts optional `collaborators` and `rehydrateFromSessionId`.
- `GET /sessions/{session_id}/rehydrate` returns canonical papers seen in that session.
- `POST /sessions/{session_id}/collaborators/{name}` adds a collaborator and emits a live event.
- GraphQL subscription `collaboratorEvent(sessionId: ID!)` streams join/presence through Cosmo EDFS.

---

## Architecture

```
React (Vite, :5173)
     |         \
     | REST     \ GraphQL subscribe over SSE
     v          v
FastAPI (:8000)   Cosmo Router (:3002, Go binary, Docker)
     |                    |
     |  async agent loop  | SUBSCRIBE redis channels
     v                    v
TinyFish Agent API  <--- Redis (:6379, Redis Stack) ---> FastAPI publishers
     |                    ^
     | run-sse stream     | XREADGROUP by normalizer worker
     v                    |
 streaming_url ----> Redis stream (raw_extract) -> worker normalization
 (iframe in UI)
```

The Cosmo “event-driven subgraph” is **a schema file** with `@edfs__redisSubscribe`. The Router connects to Redis and fans out to SSE/WebSocket clients.

---

## Quick sponsor → file map

| Sponsor | Primary locations | Demo signal |
| --- | --- | --- |
| **TinyFish** | `tinyfish_runner.py`, `mock_stream.py`, `discovery.py` | Live iframe; streaming logs; structured completion enqueued |
| **Redis** | `redis_client.py`, `workers/normalizer.py`, `context_engine.py` | `MONITOR` / `XLEN` / Pub/Sub activity during a run |
| **WunderGraph Cosmo** | `router/subgraphs/*.graphql`, `router/config.json`, `frontend/src/api/graphqlClient.ts` | `/graphql` subscriptions firing `nodeAdded`, `collaboratorEvent`, etc. |

More detailed verification steps: [SPONSOR_USAGE_DETAILED.md](SPONSOR_USAGE_DETAILED.md).

---

## Prerequisites

- Docker + Docker Compose
- Node.js >= 20
- Python >= 3.11
- `wgc` CLI: `npm install -g wgc@latest` (composes the subgraph schema into the Router's `config.json`)

## First-time setup

```bash
# 1. Copy env template
cp .env.example .env
# Fill in TINYFISH_API_KEY when available.
# If you don't have a key yet, edit .env and set MOCK_TINYFISH=1 for first run.

# 2. Compose the Cosmo Router config from the subgraph schema
cd router && npm install && npm run compose && cd ..

# 3. Boot Redis + Cosmo Router
docker compose up -d

# 4. Install backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
cd ..

# 5. Install frontend
cd frontend && npm install && cd ..
```

If you use Cosmo cloud-authenticated CLI operations, set:

- `WGC_API_KEY=<your_cosmo_key>`

## Daily dev loop

One command boots everything (Redis + Cosmo Router + backend + frontend) with prefixed, interleaved logs:

```bash
./run.sh
```

Ctrl+C shuts down the dev servers cleanly. Infra (Redis + Cosmo) stays up in the background; stop it with `docker compose down`.

Useful flags:

- `./run.sh --setup-only` — install deps + compose the Cosmo Router config, then exit.
- `./run.sh --no-infra` — skip `docker compose` (infra already up).
- `./run.sh --fresh` — `docker compose down` first, then start clean.

Open http://localhost:5173, type a topic, watch the graph assemble.

## Mock mode

If you don't have TinyFish credits yet, set `MOCK_TINYFISH=1` in `.env`. The backend will generate a realistic entity stream on a timer so the whole UI (graph, panels, timeline, replay) is fully functional without burning real API calls.

## PhD mode runtime flags

Use these in `.env` to turn on citation-focused academic crawling:

- `ACADEMIC_MODE=1` (default)
- `CITATION_TRAVERSAL_DEPTH=1`
- `CITATION_BRANCH_LIMIT=5`
- `ALLOWED_ACADEMIC_DOMAINS=arxiv.org,semanticscholar.org,pubmed.ncbi.nlm.nih.gov,scholar.google.com`

These flags bias TinyFish toward academic sources, extract canonical paper fields, and expand references/cited-by chains while keeping traversal bounded for demo stability.

## Hackathon day

Follow [HACKATHON_DAY.md](HACKATHON_DAY.md) top-to-bottom on the day of the event. It covers booth questions, smoke tests, the 3-minute demo script, and troubleshooting.

## Notable deviations from `Project Details.md`

- TinyFish docs are at `docs.tinyfish.ai` (not `.io`). Auth is `X-API-Key`.
- TinyFish has no "screenshot-per-page" endpoint. Each run emits one `streaming_url` for iframe-embeddable live preview. `BrowserSnapshotEvent` is replaced by a single cached `streaming_url` per session.
- Cosmo Streams (EDFS) over Redis means we don't need a Node.js subgraph for subscriptions.
- TinyFish `output_schema` is a JSON Schema **subset** (no `oneOf`, no `additionalProperties`, no `const`; use `anyOf` and `nullable: true`).

## Current readiness note

At the moment, `wgc router compose` can fail depending on the active Cosmo EDFS validation rules for event-driven schemas. If `router/config.json` is not generated, run setup will stop before infra starts.

Use this recovery order:

1. `cd router && npm run compose`
2. fix any schema composition errors shown by `wgc`
3. rerun `./run.sh --fresh`
