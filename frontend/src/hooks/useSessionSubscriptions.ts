import { useEffect } from "react";
import { useClient } from "urql";
import { pipe, subscribe as wonkaSubscribe } from "wonka";
import {
  AGENT_STATUS_CHANGED,
  COLLABORATOR_EVENT,
  CRAWL_LOG,
  EDGE_LINKED,
  NODE_ADDED,
} from "../api/subscriptions";
import { useNexusStore } from "../store/nexus";
import type {
  AgentStatusChangedEvent,
  CrawlLogEntry,
  CrawlLogStreamEvent,
  EdgeLinkedEvent,
  NodeAddedEvent,
  AgentStatus,
  Entity,
  Relationship,
  SessionCollaboratorEvent,
  SessionCollaboratorStreamEvent,
} from "../types/schema";

/**
 * Subscribe to Nexus live streams from the Cosmo Router. Each subscription
 * is routed to its corresponding Zustand setter.
 *
 * The hook is stable across re-renders of the session page - when `sessionId`
 * changes, the previous subscriptions are torn down and re-created.
 */
export function useSessionSubscriptions(sessionId: string | null) {
  const client = useClient();
  const addNode = useNexusStore((s) => s.addNode);
  const addEdge = useNexusStore((s) => s.addEdge);
  const setAgentStatus = useNexusStore((s) => s.setAgentStatus);
  const appendLog = useNexusStore((s) => s.appendLog);
  const upsertCollaborator = useNexusStore((s) => s.upsertCollaborator);
  const markSubscriptionEvent = useNexusStore((s) => s.markSubscriptionEvent);
  const resetSubscriptionHealth = useNexusStore((s) => s.resetSubscriptionHealth);

  useEffect(() => {
    if (!sessionId) return;
    resetSubscriptionHealth();

    const unsubNode = pipe(
      client.subscription<{ nodeAdded: NodeAddedEvent }>(NODE_ADDED, { sessionId }),
      wonkaSubscribe(({ data, error }) => {
        if (error) console.warn("nodeAdded error", error);
        if (data?.nodeAdded?.id) {
          const decoded = decodeEventPayload<{ entity?: Entity }>(data.nodeAdded.id);
          if (decoded?.entity) {
            addNode(decoded.entity);
            markSubscriptionEvent();
          }
        }
      }),
    );

    const unsubEdge = pipe(
      client.subscription<{ edgeLinked: EdgeLinkedEvent }>(EDGE_LINKED, { sessionId }),
      wonkaSubscribe(({ data, error }) => {
        if (error) console.warn("edgeLinked error", error);
        if (data?.edgeLinked?.id) {
          const decoded = decodeEventPayload<{ relationship?: Relationship }>(data.edgeLinked.id);
          if (decoded?.relationship) {
            addEdge(decoded.relationship);
            markSubscriptionEvent();
          }
        }
      }),
    );

    const unsubAgent = pipe(
      client.subscription<{ agentStatusChanged: AgentStatusChangedEvent }>(
        AGENT_STATUS_CHANGED,
        { sessionId },
      ),
      wonkaSubscribe(({ data, error }) => {
        if (error) console.warn("agentStatusChanged error", error);
        if (data?.agentStatusChanged?.id) {
          const decoded = decodeEventPayload<{ status?: AgentStatus }>(data.agentStatusChanged.id);
          if (decoded?.status) {
            setAgentStatus(decoded.status);
            markSubscriptionEvent();
          }
        }
      }),
    );

    const unsubLog = pipe(
      client.subscription<{ crawlLog: CrawlLogStreamEvent }>(CRAWL_LOG, { sessionId }),
      wonkaSubscribe(({ data, error }) => {
        if (error) console.warn("crawlLog error", error);
        if (data?.crawlLog?.id) {
          const decoded = decodeEventPayload<CrawlLogEntry>(data.crawlLog.id);
          if (decoded) {
            appendLog(decoded);
            markSubscriptionEvent();
          }
        }
      }),
    );

    const unsubCollaborator = pipe(
      client.subscription<{ collaboratorEvent: SessionCollaboratorStreamEvent }>(
        COLLABORATOR_EVENT,
        { sessionId },
      ),
      wonkaSubscribe(({ data, error }) => {
        if (error) console.warn("collaboratorEvent error", error);
        if (data?.collaboratorEvent?.id) {
          const decoded = decodeEventPayload<{
            sessionId: string;
            collaborator: string;
            action: string;
            updatedAt: string;
          }>(data.collaboratorEvent.id);
          if (decoded) {
            upsertCollaborator(decoded);
            markSubscriptionEvent();
          }
        }
      }),
    );

    return () => {
      unsubNode.unsubscribe();
      unsubEdge.unsubscribe();
      unsubAgent.unsubscribe();
      unsubLog.unsubscribe();
      unsubCollaborator.unsubscribe();
    };
  }, [
    sessionId,
    client,
    addNode,
    addEdge,
    setAgentStatus,
    appendLog,
    upsertCollaborator,
    markSubscriptionEvent,
    resetSubscriptionHealth,
  ]);
}

function decodeEventPayload<T>(encodedId: string): T | null {
  try {
    const idx = encodedId.indexOf(":");
    if (idx < 0) return null;
    const b64raw = encodedId.slice(idx + 1).replace(/-/g, "+").replace(/_/g, "/");
    const pad = b64raw.length % 4;
    const b64 = pad ? b64raw + "=".repeat(4 - pad) : b64raw;
    const json = atob(b64);
    return JSON.parse(json) as T;
  } catch (e) {
    console.warn("Failed decoding EDFS payload", e);
    return null;
  }
}
