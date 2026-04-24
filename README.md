# Nexus

> Live knowledge-graph research cockpit for the "Ship to Prod - Agentic Engineering" hackathon, San Francisco.

A user types a topic. A TinyFish web agent autonomously browses the live web while a React UI renders a D3 force-directed graph that assembles itself node-by-node in real time. Sponsors: **TinyFish** (web agent) + **WunderGraph Cosmo** (real-time GraphQL federation via EDFS over Redis) + **Redis** (streams + normalization + context + timeline).

## PhD research positioning

Nexus is designed for research pain points that common literature tools do not solve well:

- citation rabbit holes that lose context
- static citation graphs that do not keep discovering live
- no continuity across sessions
- manual synthesis of related papers
- advisor meetings that require a clear narrative, not a raw paper list

### Sponsor features used for this use case

- **TinyFish**: academic-source targeting (arXiv, Semantic Scholar, PubMed, Google Scholar, lab pages), realtime `agent.stream`, `output_schema`, and citation-chain traversal (references + cited-by expansion).
- **Redis**: Redis Streams for normalization pipeline, dedupe (`BF.ADD`), replayable session memory (`ZADD`), realtime fanout (`PUBLISH`), and context retrieval over canonical docs.
- **WunderGraph Cosmo**: EDFS subscriptions over Redis for collaborative live sessions where multiple clients follow the same research graph.

### Sponsor-to-sponsor flow

`Query -> TinyFish extraction -> Redis stream normalization worker -> Redis canonical/context store + pub/sub -> Cosmo realtime subscriptions -> shared graph across collaborators`

### New API capabilities (implemented)

- `POST /sessions` accepts optional `collaborators` and `rehydrateFromSessionId`.
- `GET /sessions/{session_id}/rehydrate` returns canonical papers seen in that session.
- `POST /sessions/{session_id}/collaborators/{name}` adds a collaborator and emits a live event.
- GraphQL subscription `collaboratorEvent(sessionId: ID!)` streams join/presence updates through Cosmo EDFS.

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
TinyFish Agent API  <--- Redis (:6379, with RedisBloom) ---> FastAPI publishers
     |                    ^
     | run-sse stream     | XREADGROUP by normalizer worker
     v                    |
 streaming_url ----> Redis stream (raw_extract) -> worker normalization
 (iframe in UI)
```

The Cosmo "event-driven subgraph" is **just a schema file** (`router/subgraphs/research.graphql`) with `@edfs__redisSubscribe` directives. There is no subscription server to run - the Router connects directly to Redis and fans out to SSE/WS clients.

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

## Sponsor integration map

| Sponsor | Where it lives | Demo proof |
|---|---|---|
| **TinyFish** | `backend/app/tinyfish_runner.py` drives `AsyncTinyFish.agent.stream`. Live browser iframe in `AgentPanel.tsx` uses the `streaming_url` SSE event. Structured paper extraction via `output_schema` and citation-chain hints. | Live iframe; `NEXUS_OUTPUT_SCHEMA` in code |
| **WunderGraph Cosmo** | `router/subgraphs/research.graphql` (zero-code event-driven subgraph with `@edfs__redisSubscribe`). Includes `collaboratorEvent` realtime stream. Router in Docker. | `/graphql` endpoint, SSE trace of `nodeAdded` and `collaboratorEvent` |
| **Redis** | `backend/app/redis_client.py` uses Streams (`XADD`/`XREADGROUP`) for normalization jobs, `BF.ADD` for URL dedup, `ZADD` for timeline, `PUBLISH` for realtime events, and canonical/context keys for cross-session reuse. Local Docker Redis is the default runtime. | `redis-cli MONITOR` + stream depth (`XLEN`) during demo |

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
