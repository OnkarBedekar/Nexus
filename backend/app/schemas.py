"""Pydantic v2 mirrors of the canonical Nexus types.

These shapes match `router/subgraphs/research.graphql`. When we publish to
Redis the JSON MUST include the GraphQL `__typename` field or the Cosmo
Router will reject the event. The publishers in `redis_client.py` inject
`__typename` automatically.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


def utcnow_iso() -> str:
    """Deterministic ISO-8601 timestamp with UTC timezone marker."""
    return datetime.now(tz=timezone.utc).isoformat()


class EntityType(str, Enum):
    company = "company"
    person = "person"
    concept = "concept"
    claim = "claim"
    paper = "paper"


class AgentState(str, Enum):
    idle = "idle"
    browsing = "browsing"
    extracting = "extracting"
    queuing = "queuing"
    done = "done"
    error = "error"


class LogLevel(str, Enum):
    info = "info"
    warn = "warn"
    error = "error"


class TimelineEventType(str, Enum):
    query_started = "query_started"
    page_visited = "page_visited"
    fact_extracted = "fact_extracted"
    entity_normalized = "entity_normalized"
    edge_created = "edge_created"
    duplicate_skipped = "duplicate_skipped"
    agent_error = "agent_error"


class SessionStatus(str, Enum):
    active = "active"
    paused = "paused"
    complete = "complete"


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str
    title: str
    extractedAt: str = Field(default_factory=utcnow_iso)
    rationale: str | None = None
    excerpt: str | None = Field(
        default=None,
        description="3-5 sentences from the page that mention this entity. Used by the SourcePreviewDrawer.",
    )


class Entity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    type: EntityType
    aliases: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    firstSeen: str = Field(default_factory=utcnow_iso)
    lastSeen: str = Field(
        default_factory=utcnow_iso,
        description="Most recent time this entity was (re-)observed. The frontend displays this in the detail panel.",
    )
    confidence: float = 0.7


class CanonicalPaper(BaseModel):
    model_config = ConfigDict(extra="ignore")

    paperId: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    arxivId: str | None = None
    citationCount: int | None = None
    abstract: str | None = None
    methodology: str | None = None
    keyFindings: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    citedBy: list[str] = Field(default_factory=list)
    sourceUrl: str | None = None
    confidence: float = 0.7


class Relationship(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    fromId: str
    toId: str
    predicate: str
    confidence: float = 0.7
    sources: list[SourceRef] = Field(default_factory=list)
    createdAt: str = Field(default_factory=utcnow_iso)


class AgentStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sessionId: str
    state: AgentState
    currentUrl: str | None = None
    streamingUrl: str | None = None
    queueLength: int = 0
    pagesVisited: int = 0
    lastAction: str = ""
    updatedAt: str = Field(default_factory=utcnow_iso)


class CrawlLogEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sessionId: str
    timestamp: str = Field(default_factory=utcnow_iso)
    level: LogLevel = LogLevel.info
    message: str
    url: str | None = None


class TimelineEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sessionId: str
    sequenceNumber: int
    type: TimelineEventType
    timestamp: str = Field(default_factory=utcnow_iso)
    label: str
    entityId: str | None = None
    relationshipId: str | None = None
    url: str | None = None


class SessionStats(BaseModel):
    nodes: int = 0
    edges: int = 0
    pages: int = 0
    elapsedSeconds: int = 0


class ResearchSession(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    topic: str
    startedAt: str = Field(default_factory=utcnow_iso)
    status: SessionStatus = SessionStatus.active
    stats: SessionStats = Field(default_factory=SessionStats)
    seedUrl: str | None = None
    runId: str | None = None
    streamingUrl: str | None = None
    collaborators: list[str] = Field(default_factory=list)
    # Two-phase: discover URLs first, then run the agent per URL (faster, bounded work).
    useTwoPhase: bool = True
    maxDiscoverUrls: int = 12
    activePhase: str | None = None
    # "discovering" | "extracting" | "complete"
    discoveredUrls: list[str] = Field(default_factory=list)
    currentExtractionIndex: int = 0
    extractionUrlCount: int = 0


# --- Request / response shapes for the REST API ---


class StartSessionRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    seedUrl: str | None = Field(
        default=None,
        description="Optional override. Defaults to a TinyFish Search result for the topic.",
    )
    collaborators: list[str] = Field(default_factory=list)
    rehydrateFromSessionId: str | None = None
    useTwoPhase: bool = Field(
        default=True,
        description="If true, discover a bounded set of source URLs, then run the agent on each. If false, legacy single-run behavior.",
    )
    maxDiscoverUrls: int = Field(12, ge=1, le=25, description="Max URLs from phase-1 discovery")


class SessionCollaboratorEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sessionId: str
    collaborator: str
    action: str = "joined"
    updatedAt: str = Field(default_factory=utcnow_iso)
