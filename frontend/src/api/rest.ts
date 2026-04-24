import type { ResearchSession } from "../types/schema";

const BACKEND = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";

async function json<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const resp = await fetch(input, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw new Error(`${resp.status} ${resp.statusText}: ${body}`);
  }
  return resp.json() as Promise<T>;
}

export async function startSession(params: {
  topic: string;
  seedUrl?: string;
  collaborators?: string[];
}): Promise<ResearchSession> {
  return json<ResearchSession>(`${BACKEND}/sessions`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function getSession(id: string): Promise<ResearchSession> {
  return json<ResearchSession>(`${BACKEND}/sessions/${id}`);
}

export async function listSessions(): Promise<ResearchSession[]> {
  return json<ResearchSession[]>(`${BACKEND}/sessions`);
}

export async function pauseSession(id: string): Promise<ResearchSession> {
  return json<ResearchSession>(`${BACKEND}/sessions/${id}/pause`, { method: "POST" });
}

export async function addCollaborator(id: string, name: string): Promise<ResearchSession> {
  return json<ResearchSession>(
    `${BACKEND}/sessions/${id}/collaborators/${encodeURIComponent(name)}`,
    { method: "POST" },
  );
}

export async function getStreamingUrl(id: string): Promise<string | null> {
  try {
    const resp = await json<{ streamingUrl: string | null }>(
      `${BACKEND}/agent/${id}/snapshot-url`,
    );
    return resp.streamingUrl;
  } catch {
    return null;
  }
}

export async function getSessionContext(
  id: string,
  query: string,
): Promise<{ sessionId: string; query: string; results: Array<Record<string, unknown>> }> {
  const qs = new URLSearchParams({ query });
  return json(`${BACKEND}/sessions/${id}/context?${qs.toString()}`);
}

export async function getRelatedContext(
  id: string,
): Promise<{ sessionId: string; results: Array<Record<string, unknown>> }> {
  return json(`${BACKEND}/sessions/${id}/related`);
}
