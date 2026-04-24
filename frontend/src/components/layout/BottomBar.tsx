import { useEffect, useState } from "react";
import { useNexusStore } from "../../store/nexus";

export function BottomBar() {
  const session = useNexusStore((s) => s.session);
  const crawlLog = useNexusStore((s) => s.crawlLog);
  const nodes = useNexusStore((s) => s.nodes);
  const edges = useNexusStore((s) => s.edges);
  const agent = useNexusStore((s) => s.agentStatus);

  const elapsed = useElapsedSince(session?.startedAt);
  const lastLog = crawlLog[crawlLog.length - 1];

  return (
    <div className="relative flex items-center justify-between gap-4 px-4 py-1.5 border-t border-cyber-border bg-cyber-panel text-xs overflow-hidden">
      {/* Subtle top edge accent — mirrors the header's illuminated bar. */}
      <div
        className="absolute inset-x-0 top-0 h-px pointer-events-none"
        style={{
          background:
            "linear-gradient(90deg, transparent, rgba(0, 212, 255, 0.3) 50%, transparent)",
        }}
      />

      {/* Terminal prompt showing the last crawl log line. */}
      <div className="min-w-0 flex-1 truncate font-mono flex items-center gap-1.5">
        <span className="text-cyber-tertiary flex-shrink-0">nexus@sess</span>
        <span className="text-cyber-textDim flex-shrink-0">:~$</span>
        {lastLog ? (
          <>
            <span className="text-cyber-text truncate">{lastLog.message}</span>
            {lastLog.url ? (
              <span className="text-cyber-textDim truncate">
                <span className="text-cyber-accent mx-1">⌁</span>
                {lastLog.url}
              </span>
            ) : null}
          </>
        ) : (
          <span className="text-cyber-textDim">waiting for agent</span>
        )}
        <span
          className="inline-block w-1.5 h-3 bg-cyber-accent animate-blink ml-0.5 flex-shrink-0"
          style={{ boxShadow: "0 0 4px #00d4ff" }}
          aria-hidden
        />
      </div>

      <div className="flex items-center gap-3 font-mono tabular-nums font-hud text-[10px] tracking-[0.2em] uppercase text-cyber-textDim flex-shrink-0">
        <Stat label="nodes" value={nodes.size} color="#00ff88" />
        <Stat label="edges" value={edges.size} color="#00d4ff" />
        <Stat label="pages" value={agent?.pagesVisited ?? 0} color="#ff00ff" />
        <Stat
          label="queue"
          value={agent?.queueLength ?? 0}
          color="#ffaa00"
        />
        {session?.useTwoPhase && session?.activePhase && (
          <span
            className="text-[9px] tracking-wide font-mono text-cyber-warn max-w-[200px] truncate"
            title={
              session.discoveredUrls?.length
                ? session.discoveredUrls.join(" · ")
                : undefined
            }
          >
            {session.activePhase === "discovering" && "Phase 1 · discovering URLs"}
            {session.activePhase === "extracting" &&
              (session.extractionUrlCount ?? 0) > 0 &&
              `Phase 2 · source ${(session.currentExtractionIndex ?? 0) + 1}/${session.extractionUrlCount ?? 0}`}
            {session.activePhase === "complete" && "Two-phase complete"}
          </span>
        )}
        <span className="flex items-center gap-1.5">
          <span className="text-cyber-textDim">T+</span>
          <span
            className="text-cyber-accent tabular-nums"
            style={{ textShadow: "0 0 4px rgba(0, 212, 255, 0.6)" }}
          >
            {elapsed}
          </span>
        </span>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <span className="flex items-center gap-1">
      <span>{label}</span>
      <span
        style={{
          color,
          textShadow: `0 0 4px ${color}66`,
        }}
      >
        {value}
      </span>
    </span>
  );
}

function useElapsedSince(iso?: string) {
  const [_, tick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => tick((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, []);
  if (!iso) return "0:00";
  const start = new Date(iso).getTime();
  const now = Date.now();
  const sec = Math.max(0, Math.floor((now - start) / 1000));
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}
