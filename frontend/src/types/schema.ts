// Mirror of `backend/app/schemas.py` and `router/subgraphs/research.graphql`.
// Keep these in sync manually - they're small enough that codegen would be overkill for a hackathon.

export type EntityType = "company" | "person" | "concept" | "claim" | "paper";
export type AgentState =
  | "idle"
  | "browsing"
  | "extracting"
  | "queuing"
  | "done"
  | "error";
export type LogLevel = "info" | "warn" | "error";
export type TimelineEventType =
  | "query_started"
  | "page_visited"
  | "fact_extracted"
  | "entity_normalized"
  | "edge_created"
  | "duplicate_skipped"
  | "agent_error";
export type SessionStatus = "active" | "paused" | "complete";

export interface SourceRef {
  url: string;
  title: string;
  extractedAt: string;
  rationale?: string | null;
  excerpt?: string | null;
}

export interface Entity {
  id: string;
  name: string;
  type: EntityType;
  aliases: string[];
  claims: string[];
  sources: SourceRef[];
  firstSeen: string;
  lastSeen: string;
  confidence: number;
}

export interface Relationship {
  id: string;
  fromId: string;
  toId: string;
  predicate: string;
  confidence: number;
  sources: SourceRef[];
  createdAt: string;
}

export interface AgentStatus {
  sessionId: string;
  state: AgentState;
  currentUrl?: string | null;
  streamingUrl?: string | null;
  queueLength: number;
  pagesVisited: number;
  lastAction: string;
  updatedAt: string;
}

export interface CrawlLogEntry {
  sessionId: string;
  timestamp: string;
  level: LogLevel;
  message: string;
  url?: string | null;
}

export interface TimelineEvent {
  sessionId: string;
  sequenceNumber: number;
  type: TimelineEventType;
  timestamp: string;
  label: string;
  entityId?: string | null;
  relationshipId?: string | null;
  url?: string | null;
}

export interface SessionStats {
  nodes: number;
  edges: number;
  pages: number;
  elapsedSeconds: number;
}

export interface ResearchSession {
  id: string;
  topic: string;
  startedAt: string;
  status: SessionStatus;
  stats: SessionStats;
  seedUrl?: string | null;
  runId?: string | null;
  streamingUrl?: string | null;
  collaborators: string[];
}

// --- Subscription payload shapes from Cosmo ---

export interface NodeAddedEvent {
  id: string;
}
export interface EdgeLinkedEvent {
  id: string;
}
export interface AgentStatusChangedEvent {
  id: string;
}
export interface CrawlLogStreamEvent {
  id: string;
}
export interface SessionCollaboratorStreamEvent {
  id: string;
}

export interface SessionCollaboratorEvent {
  sessionId: string;
  collaborator: string;
  action: string;
  updatedAt: string;
}

