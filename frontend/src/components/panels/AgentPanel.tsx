import { useEffect, useState } from "react";
import { getStreamingUrl } from "../../api/rest";
import { useNexusStore } from "../../store/nexus";

export function AgentPanel() {
  const session = useNexusStore((s) => s.session);
  const agent = useNexusStore((s) => s.agentStatus);
  const crawlLog = useNexusStore((s) => s.crawlLog);
  const setPreviewExpanded = useNexusStore((s) => s.setPreviewExpanded);

  const [streamingUrl, setStreamingUrl] = useState<string | null>(null);

  // Prefer the URL carried by the agent status subscription. Fall back to
  // polling the REST endpoint once after the session opens in case the
  // subscription missed the STREAMING_URL event (they can race).
  useEffect(() => {
    if (agent?.streamingUrl) {
      setStreamingUrl(agent.streamingUrl);
      return;
    }
    if (!session) return;
    let cancelled = false;
    (async () => {
      // Give the runner a few seconds to start and grab the URL.
      for (let i = 0; i < 10 && !cancelled; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        const url = await getStreamingUrl(session.id);
        if (url) {
          if (!cancelled) setStreamingUrl(url);
          return;
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [agent?.streamingUrl, session?.id]);

  const last5Logs = crawlLog.slice(-5).reverse();
  const isLiveAgent =
    agent?.state === "browsing" || agent?.state === "extracting";

  return (
    <aside className="panel flex flex-col h-full overflow-hidden">
      {/* ------------------------------------------------------------------
          Live browser snapshot.
          ------------------------------------------------------------------ */}
      <div className="relative border-b border-nexus-border">
        <div className="flex items-center justify-between px-3 py-1.5 bg-nexus-surfaceAlt/60 border-b border-nexus-border">
          <span className="font-hud text-[10px] tracking-[0.25em] text-cyber-textDim uppercase">
            ◉ Live preview
          </span>
          <div className="flex items-center gap-2">
            {isLiveAgent && (
              <span
                className="font-hud text-[10px] tracking-[0.3em] text-cyber-danger"
                style={{ textShadow: "0 0 8px rgba(255, 51, 102, 0.7)" }}
              >
                ● ACTIVE
              </span>
            )}
            <button
              type="button"
              className="btn !px-2 !py-1 text-[10px]"
              onClick={() => setPreviewExpanded(true)}
            >
              Expand
            </button>
          </div>
        </div>
        <div className="h-[170px] bg-black relative overflow-hidden">
          {streamingUrl && streamingUrl !== "about:blank" ? (
            <iframe
              title="TinyFish live browser"
              src={streamingUrl}
              className="w-full h-full border-0"
              sandbox="allow-same-origin allow-scripts"
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center text-cyber-textDim text-xs text-center px-4 font-mono">
              {streamingUrl === "about:blank" ? (
                <span>
                  <span className="block text-cyber-warn mb-1">
                    [MOCK MODE]
                  </span>
                  live browser preview disabled.
                  <br />
                  real runs show a TinyFish{" "}
                  <code className="text-cyber-accent">streaming_url</code>{" "}
                  here.
                </span>
              ) : session ? (
                <span className="flex flex-col items-center gap-2">
                  <span className="inline-flex items-center gap-2 text-cyber-accent">
                    <span
                      className="w-2 h-2 rounded-full bg-cyber-accent"
                      style={{ boxShadow: "0 0 6px #00d4ff" }}
                    />
                    establishing link...
                  </span>
                  <span className="text-[10px]">
                    waiting for TinyFish session
                  </span>
                </span>
              ) : (
                <span>Start a session to see the live browser.</span>
              )}
            </div>
          )}
          {/* CRT scanline overlay painted on top of the iframe so the feed
              always feels like a surveillance monitor. */}
          <div
            className="absolute inset-0 pointer-events-none"
            aria-hidden
            style={{
              background:
                "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0, 0, 0, 0.35) 2px, rgba(0, 0, 0, 0.35) 3px)",
            }}
          />
          <LiveBadge active={isLiveAgent} />
        </div>
        {agent?.currentUrl && (
          <div className="px-3 py-1.5 text-[10.5px] font-mono text-cyber-accent truncate border-t border-cyber-border bg-cyber-panel">
            <span className="text-cyber-textDim">GET</span>{" "}
            <span className="text-cyber-text">{agent.currentUrl}</span>
          </div>
        )}
      </div>

      <div className="p-3 border-b border-cyber-border">
        <div className="text-sm font-mono text-cyber-text truncate">
          {agent?.lastAction || <span className="text-cyber-textDim">No active steps</span>}
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        <div className="px-3 py-2 font-hud text-[10.5px] tracking-[0.25em] text-cyber-textDim uppercase flex items-center justify-between">
          <span>Activity log</span>
          <span className="font-mono tabular-nums text-cyber-textDim">{crawlLog.length}</span>
        </div>
        <ul className="px-3 pb-3 space-y-1 scrollbar-thin overflow-y-auto max-h-full">
          {last5Logs.length === 0 ? (
            <li className="text-xs font-mono text-cyber-textDim flex items-center gap-1.5">
              <span className="text-cyber-accent">{">"}</span> no activity yet
              <span
                className="inline-block w-1.5 h-3 bg-cyber-textDim animate-blink"
                aria-hidden
              />
            </li>
          ) : (
            last5Logs.map((e, i) => (
              <li
                key={`${e.timestamp}-${i}`}
                className="text-[11.5px] font-mono text-cyber-text animate-slide-in-bottom leading-snug"
              >
                <span className="text-cyber-accent">❯</span>{" "}
                <span className="text-cyber-textDim">
                  [{formatTime(e.timestamp)}]
                </span>{" "}
                <span>{e.message}</span>
              </li>
            ))
          )}
        </ul>
      </div>
    </aside>
  );
}

function LiveBadge({ active }: { active: boolean }) {
  if (!active) return null;
  return (
    <div
      className="absolute top-2 right-2 flex items-center gap-1.5 px-2 py-0.5 bg-black/80 backdrop-blur font-hud text-[10px] tracking-[0.3em] uppercase text-cyber-danger"
      style={{
        border: "1px solid rgba(255, 51, 102, 0.7)",
        boxShadow:
          "0 0 6px rgba(255, 51, 102, 0.5), inset 0 0 8px rgba(255, 51, 102, 0.15)",
      }}
    >
      <span
        className="inline-flex rounded-full h-2 w-2 bg-cyber-danger"
        style={{ boxShadow: "0 0 6px #ff3366" }}
      />
      <span>Active</span>
    </div>
  );
}


function formatTime(iso: string) {
  const d = new Date(iso);
  return `${d.getHours().toString().padStart(2, "0")}:${d
    .getMinutes()
    .toString()
    .padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}`;
}
