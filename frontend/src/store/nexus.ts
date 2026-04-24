import { create } from "zustand";
import type {
  AgentStatus,
  CrawlLogEntry,
  Entity,
  Relationship,
  ResearchSession,
  SourceRef,
  SessionCollaboratorEvent,
} from "../types/schema";

interface NexusStore {
  // --- Session ---
  session: ResearchSession | null;
  setSession: (s: ResearchSession | null) => void;
  upsertCollaborator: (evt: SessionCollaboratorEvent) => void;

  // --- Graph data ---
  nodes: Map<string, Entity>;
  edges: Map<string, Relationship>;
  addNode: (e: Entity) => void;
  addEdge: (r: Relationship) => void;
  clearGraph: () => void;

  // --- Selection ---
  selectedNodeId: string | null;
  selectNode: (id: string | null) => void;

  // --- Agent ---
  agentStatus: AgentStatus | null;
  setAgentStatus: (s: AgentStatus) => void;

  // --- Crawl log (FIFO capped) ---
  crawlLog: CrawlLogEntry[];
  appendLog: (e: CrawlLogEntry) => void;

  // --- Subscription diagnostics ---
  subscriptionLastEventAt: string | null;
  subscriptionEventCount: number;
  markSubscriptionEvent: () => void;
  resetSubscriptionHealth: () => void;

  // --- Source preview drawer ---
  previewSourceUrl: string | null;
  openSourcePreview: (url: string | null) => void;

  // --- Live preview modal ---
  isPreviewExpanded: boolean;
  setPreviewExpanded: (expanded: boolean) => void;

  // --- Final report modal ---
  isFinalReportOpen: boolean;
  setFinalReportOpen: (open: boolean) => void;
}

export const useNexusStore = create<NexusStore>((set) => ({
  session: null,
  setSession: (session) => set({ session }),
  upsertCollaborator: (evt) =>
    set((s) => {
      if (!s.session || s.session.id !== evt.sessionId) return {};
      const next = new Set(s.session.collaborators ?? []);
      if (evt.action === "joined") next.add(evt.collaborator);
      if (evt.action === "left") next.delete(evt.collaborator);
      return { session: { ...s.session, collaborators: Array.from(next) } };
    }),

  nodes: new Map(),
  edges: new Map(),
  addNode: (entity) =>
    set((s) => {
      if (s.nodes.has(entity.id)) {
        // Merge: keep claims and sources accreting over time.
        // firstSeen = earliest observation; lastSeen = most recent.
        const existing = s.nodes.get(entity.id)!;
        const firstSeen = earlier(existing.firstSeen, entity.firstSeen);
        const lastSeen = later(existing.lastSeen, entity.lastSeen ?? entity.firstSeen);
        const merged: Entity = {
          ...existing,
          ...entity,
          firstSeen,
          lastSeen,
          // Take the higher confidence: successive sightings should only
          // ever corroborate, not downgrade, an entity.
          confidence: Math.max(existing.confidence, entity.confidence),
          claims: Array.from(new Set([...existing.claims, ...entity.claims])),
          sources: mergeSourcesBy(existing.sources, entity.sources, "url"),
        };
        const nodes = new Map(s.nodes);
        nodes.set(entity.id, merged);
        return { nodes };
      }
      const nodes = new Map(s.nodes);
      // Backfill lastSeen in case the server didn't provide it (older payloads).
      nodes.set(entity.id, { ...entity, lastSeen: entity.lastSeen ?? entity.firstSeen });
      return { nodes };
    }),
  addEdge: (rel) =>
    set((s) => {
      const edges = new Map(s.edges);
      edges.set(rel.id, rel);
      return { edges };
    }),
  clearGraph: () =>
    set({
      nodes: new Map(),
      edges: new Map(),
      selectedNodeId: null,
      isFinalReportOpen: false,
    }),

  selectedNodeId: null,
  selectNode: (selectedNodeId) => set({ selectedNodeId }),

  agentStatus: null,
  setAgentStatus: (agentStatus) => set({ agentStatus }),

  crawlLog: [],
  appendLog: (entry) =>
    set((s) => ({ crawlLog: [...s.crawlLog.slice(-199), entry] })),

  subscriptionLastEventAt: null,
  subscriptionEventCount: 0,
  markSubscriptionEvent: () =>
    set((s) => ({
      subscriptionLastEventAt: new Date().toISOString(),
      subscriptionEventCount: s.subscriptionEventCount + 1,
    })),
  resetSubscriptionHealth: () =>
    set({ subscriptionLastEventAt: null, subscriptionEventCount: 0 }),

  previewSourceUrl: null,
  openSourcePreview: (url) => set({ previewSourceUrl: url }),

  isPreviewExpanded: false,
  setPreviewExpanded: (isPreviewExpanded) => set({ isPreviewExpanded }),

  isFinalReportOpen: false,
  setFinalReportOpen: (isFinalReportOpen) => set({ isFinalReportOpen }),
}));

function mergeSourcesBy(
  a: SourceRef[],
  b: SourceRef[],
  key: "url" | "title",
): SourceRef[] {
  const seen = new Map<string, SourceRef>();
  // Later observations win for fields like `excerpt`/`rationale` that may
  // be absent on the first sighting and filled in on a re-visit.
  for (const item of [...a, ...b]) {
    const k = item[key];
    const prev = seen.get(k);
    seen.set(k, prev ? { ...prev, ...stripNullish(item) } : item);
  }
  return Array.from(seen.values());
}

function stripNullish<T extends object>(obj: T): Partial<T> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(obj)) {
    if (v !== null && v !== undefined) out[k] = v;
  }
  return out as Partial<T>;
}

function earlier(a: string, b: string): string {
  return a < b ? a : b;
}
function later(a: string, b: string): string {
  return a > b ? a : b;
}
