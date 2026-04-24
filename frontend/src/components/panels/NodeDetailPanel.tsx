import { useNexusStore } from "../../store/nexus";
import { NODE_COLOR } from "../graph/colors";
import type { Entity } from "../../types/schema";

export function NodeDetailPanel() {
  const selectedId = useNexusStore((s) => s.selectedNodeId);
  const nodes = useNexusStore((s) => s.nodes);
  const openSourcePreview = useNexusStore((s) => s.openSourcePreview);
  const totalNodes = nodes.size;

  const selectedEntity = selectedId ? nodes.get(selectedId) : null;
  const reportEntity = selectedEntity ?? bestReportEntity(nodes);

  if (!reportEntity) {
    return (
      <aside className="panel h-full flex items-center justify-center p-6 relative">
        <div className="text-center space-y-3 max-w-[220px]">
          <div
            className="mx-auto w-10 h-10 flex items-center justify-center border border-cyber-border"
            style={{
              clipPath:
                "polygon(0 4px, 4px 0, calc(100% - 4px) 0, 100% 4px, 100% calc(100% - 4px), calc(100% - 4px) 100%, 4px 100%, 0 calc(100% - 4px))",
            }}
          >
            <span className="text-cyber-accent text-lg">◈</span>
          </div>
          <p className="font-hud text-[10.5px] tracking-[0.25em] text-cyber-accent uppercase">
            No target selected
          </p>
          <p className="text-xs text-cyber-textDim font-mono leading-relaxed">
            Select a node to view findings, evidence quality, and trusted sources.
          </p>
          <div className="pt-2 text-[11px] font-mono text-cyber-textDim space-y-1">
            <div>
              graph entities: <span className="text-cyber-text">{totalNodes}</span>
            </div>
          </div>
        </div>
      </aside>
    );
  }

  const color = NODE_COLOR[reportEntity.type];
  const uniqueDomains = Array.from(
    new Set(
      reportEntity.sources
        .map((s) => {
          try {
            return new URL(s.url).hostname;
          } catch {
            return s.url;
          }
        })
        .filter(Boolean),
    ),
  );

  return (
    <aside className="panel h-full flex flex-col overflow-hidden">
      <div className="relative p-4 border-b border-cyber-border hud-corners">
        <span className="hud-c-bl" aria-hidden />
        <span className="hud-c-br" aria-hidden />

        <div className="flex items-center gap-2 mb-2">
          <span className="font-hud text-[10px] tracking-[0.3em] uppercase text-cyber-textDim">
            Summary
          </span>
          <div className="flex-1 h-px bg-cyber-border" />
          <span
            className="font-hud text-[10px] tracking-[0.25em] uppercase"
            style={{ color, textShadow: `0 0 6px ${color}80` }}
          >
            {reportEntity.type}
          </span>
        </div>

        <h2
          className="font-display text-lg leading-tight tracking-wide text-cyber-text"
          style={{ textShadow: `0 0 10px ${color}55` }}
        >
          {reportEntity.name}
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {reportEntity.claims.length > 0 && (
          <section className="p-4 border-b border-cyber-border">
            <SectionLabel text="Findings" count={reportEntity.claims.length} />
            <ul className="space-y-2">
              {filterSignalClaims(reportEntity.claims).map((c, i) => (
                <li
                  key={i}
                  className="text-sm font-mono leading-snug text-cyber-text flex gap-2"
                >
                  <span className="text-cyber-accent flex-shrink-0 mt-0.5">
                    {i + 1}.
                  </span>
                  <span>{c}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {reportEntity.sources.length > 0 && (
          <section className="p-4 border-b border-cyber-border">
            <SectionLabel text="Sources" count={reportEntity.sources.length} />
            {uniqueDomains.length > 0 && (
              <div className="mb-2.5 text-[10.5px] font-mono text-cyber-textDim">{uniqueDomains.length} domain{uniqueDomains.length === 1 ? "" : "s"}</div>
            )}
            <ul className="space-y-1.5">
              {reportEntity.sources.map((s, i) => {
                let domain = s.url;
                try {
                  domain = new URL(s.url).hostname;
                } catch {
                  /* keep raw */
                }
                return (
                  <li key={`${s.url}-${i}`}>
                    <button
                      type="button"
                      className="w-full text-left p-2 bg-cyber-panelAlt border border-cyber-border hover:border-cyber-accent/70 hover:shadow-neon-cyan transition flex items-start gap-2"
                      onClick={() => openSourcePreview(s.url)}
                      style={{
                        clipPath:
                          "polygon(0 3px, 3px 0, calc(100% - 3px) 0, 100% 3px, 100% calc(100% - 3px), calc(100% - 3px) 100%, 3px 100%, 0 calc(100% - 3px))",
                      }}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-mono text-cyber-text truncate">
                          {s.title}
                        </div>
                        <div className="text-[10.5px] text-cyber-textDim font-mono truncate mt-0.5">
                          <span className="text-cyber-accent">⌁</span> {domain}
                        </div>
                        {s.rationale && (
                          <div className="text-[10.5px] text-cyber-textDim mt-1 line-clamp-2">
                            rationale: {s.rationale}
                          </div>
                        )}
                        {s.excerpt && (
                          <div className="text-[10.5px] text-cyber-text mt-1 line-clamp-2">
                            "{s.excerpt}"
                          </div>
                        )}
                        <div className="text-[10px] text-cyber-textDim mt-1">
                          extracted {relativeTime(s.extractedAt)}
                        </div>
                      </div>
                      <span
                        className="text-cyber-accent flex-shrink-0 mt-0.5"
                        style={{ textShadow: "0 0 4px #00d4ff" }}
                      >
                        →
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

      </div>
    </aside>
  );
}

/**
 * Section header in `// LABEL (n)` format with a thin trailing divider.
 * Used above every detail block to keep the HUD rhythm consistent.
 */
function SectionLabel({ text, count }: { text: string; count?: number }) {
  return (
    <div className="flex items-center gap-2 mb-2.5">
      <span className="font-hud text-[10px] tracking-[0.3em] uppercase text-cyber-accent">
        // {text}
      </span>
      {count != null && (
        <span className="font-mono text-[10.5px] text-cyber-textDim tabular-nums">
          [{count}]
        </span>
      )}
      <div className="flex-1 h-px bg-cyber-border" />
    </div>
  );
}

function filterSignalClaims(claims: string[]): string[] {
  const NOISE_PATTERNS = [
    "live crawl root topic",
    "navigate to",
    "search for papers",
    "extract details",
    "starting point",
    "research task",
  ];
  const filtered = claims.filter((c) => {
    const lc = c.toLowerCase();
    return !NOISE_PATTERNS.some((p) => lc.includes(p));
  });
  return filtered.length > 0 ? filtered : claims.slice(0, 3);
}

function bestReportEntity(nodes: Map<string, Entity>): Entity | null {
  const candidates = Array.from(nodes.values()).filter((n) => n.claims.length > 0);
  if (candidates.length === 0) return null;
  candidates.sort((a, b) => {
    const scoreA = a.confidence * 100 + a.sources.length * 5 + a.claims.length * 2;
    const scoreB = b.confidence * 100 + b.sources.length * 5 + b.claims.length * 2;
    return scoreB - scoreA;
  });
  return candidates[0] ?? null;
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const sec = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} min ago`;
  const hr = Math.floor(min / 60);
  return `${hr}h ago`;
}
