import { useEffect, useState } from "react";
import { getStreamingUrl } from "../../api/rest";
import { useNexusStore } from "../../store/nexus";

export function LivePreviewModal() {
  const expanded = useNexusStore((s) => s.isPreviewExpanded);
  const setExpanded = useNexusStore((s) => s.setPreviewExpanded);
  const session = useNexusStore((s) => s.session);
  const agent = useNexusStore((s) => s.agentStatus);
  const [streamingUrl, setStreamingUrl] = useState<string | null>(null);

  const currentUrl = agent?.currentUrl ?? session?.seedUrl ?? null;
  const isLiveAgent =
    agent?.state === "browsing" || agent?.state === "extracting";

  // Keep expanded preview in sync with the inline panel by using the same
  // fallback polling if subscription events are missed.
  useEffect(() => {
    if (agent?.streamingUrl) {
      setStreamingUrl(agent.streamingUrl);
      return;
    }
    if (!session) {
      setStreamingUrl(null);
      return;
    }
    let cancelled = false;
    (async () => {
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

  useEffect(() => {
    if (!expanded) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [expanded, setExpanded]);

  if (!expanded) return null;

  return (
    <div
      className="absolute inset-0 z-30 bg-black/70 backdrop-blur-sm flex p-3"
      onClick={() => setExpanded(false)}
    >
      <div
        className="panel panel-holo relative w-full h-full overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-2 border-b border-cyber-border bg-cyber-panelAlt/60">
          <div className="flex items-center gap-2">
            <span className="font-hud text-[10px] tracking-[0.25em] text-cyber-textDim uppercase">
              Expanded live preview
            </span>
            {isLiveAgent && (
              <span
                className="font-hud text-[10px] tracking-[0.3em] text-cyber-danger uppercase"
                style={{ textShadow: "0 0 8px rgba(255, 51, 102, 0.7)" }}
              >
                ● ACTIVE
              </span>
            )}
          </div>
          <button
            type="button"
            className="btn"
            onClick={() => setExpanded(false)}
            aria-label="Close live preview"
          >
            ✕ Close
          </button>
        </div>

        <div className="relative h-[calc(100%-72px)] bg-black">
          {streamingUrl && streamingUrl !== "about:blank" ? (
            <iframe
              title="TinyFish live browser expanded"
              src={streamingUrl}
              className="w-full h-full border-0"
              sandbox="allow-same-origin allow-scripts"
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center text-cyber-textDim text-sm text-center px-6 font-mono">
              {streamingUrl === "about:blank" ? (
                <span>
                  [MOCK MODE] live preview stream is disabled in this run.
                </span>
              ) : (
                <span>
                  Waiting for live browser preview...
                </span>
              )}
            </div>
          )}
          <div
            className="absolute inset-0 pointer-events-none"
            aria-hidden
            style={{
              background:
                "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0, 0, 0, 0.3) 2px, rgba(0, 0, 0, 0.3) 3px)",
            }}
          />
        </div>

        {currentUrl && (
          <div className="px-4 py-2 border-t border-cyber-border text-[11px] font-mono text-cyber-accent truncate">
            <span className="text-cyber-textDim">Current URL:</span>{" "}
            <span className="text-cyber-text">{currentUrl}</span>
          </div>
        )}
      </div>
    </div>
  );
}
