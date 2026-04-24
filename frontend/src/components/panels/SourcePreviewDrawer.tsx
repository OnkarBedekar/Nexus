import { useMemo } from "react";
import { useNexusStore } from "../../store/nexus";

/**
 * Overlay drawer for a specific source URL. Renders:
 *   - a title + URL + "open original" link
 *   - a highlighted excerpt from the page (entity name bolded)
 *   - a guaranteed "Why this matters" block (falls back to the first claim
 *     if the SourceRef doesn't carry a rationale yet)
 *   - every relationship this source produced for the selected entity
 *
 * Triggered when the user clicks a source row inside NodeDetailPanel.
 */
export function SourcePreviewDrawer() {
  const url = useNexusStore((s) => s.previewSourceUrl);
  const close = useNexusStore((s) => s.openSourcePreview);
  const selectedId = useNexusStore((s) => s.selectedNodeId);
  const nodes = useNexusStore((s) => s.nodes);
  const edges = useNexusStore((s) => s.edges);

  const entity = selectedId ? nodes.get(selectedId) : null;
  const source = useMemo(
    () => entity?.sources.find((s) => s.url === url) ?? null,
    [entity, url],
  );

  const relationships = useMemo(() => {
    if (!entity || !url) return [];
    return Array.from(edges.values()).filter(
      (e) =>
        (e.fromId === entity.id || e.toId === entity.id) &&
        e.sources.some((s) => s.url === url),
    );
  }, [entity, edges, url]);

  if (!url) return null;

  const rationale =
    source?.rationale ||
    entity?.claims?.[0] ||
    "No rationale recorded for this source.";
  const excerpt = source?.excerpt || null;

  return (
    <div
      className="absolute inset-0 z-20 bg-black/60 backdrop-blur-sm flex justify-end"
      onClick={() => close(null)}
    >
      <div
        className="relative w-[400px] h-full bg-cyber-panel border-l border-cyber-accent/40 overflow-y-auto scrollbar-thin animate-slide-in-right"
        onClick={(e) => e.stopPropagation()}
        style={{
          boxShadow:
            "-10px 0 40px rgba(0, 212, 255, 0.15), inset 1px 0 0 rgba(0, 212, 255, 0.3)",
        }}
      >
        {/* Neon left edge. */}
        <div
          className="absolute inset-y-0 left-0 w-px"
          style={{
            background:
              "linear-gradient(180deg, transparent, #00d4ff 20%, #00d4ff 80%, transparent)",
            boxShadow: "0 0 8px #00d4ff",
          }}
        />

        <div className="flex items-center justify-between p-3 border-b border-cyber-border sticky top-0 bg-cyber-panel/95 backdrop-blur z-10">
          <span className="font-hud text-[10px] tracking-[0.3em] uppercase text-cyber-accent flex items-center gap-2">
            <span
              className="w-1.5 h-1.5 bg-cyber-accent animate-pulse"
              style={{ boxShadow: "0 0 6px #00d4ff" }}
            />
            // classified :: source
          </span>
          <button
            type="button"
            className="font-mono text-cyber-textDim hover:text-cyber-accent text-lg leading-none w-6 h-6 flex items-center justify-center border border-cyber-border hover:border-cyber-accent/60 transition"
            onClick={() => close(null)}
            aria-label="Close"
            style={{
              clipPath:
                "polygon(0 2px, 2px 0, calc(100% - 2px) 0, 100% 2px, 100% calc(100% - 2px), calc(100% - 2px) 100%, 2px 100%, 0 calc(100% - 2px))",
            }}
          >
            ×
          </button>
        </div>

        <div className="p-4 space-y-5">
          <div>
            <div className="font-display text-base leading-snug text-cyber-text tracking-wide">
              {source?.title ?? url}
            </div>
            <div className="text-[10.5px] font-mono text-cyber-textDim mt-1.5 break-all flex items-start gap-1.5">
              <span className="text-cyber-accent">⌁</span>
              <span>{url}</span>
            </div>
          </div>

          {/* Always render "Why this matters" — the trust signal. */}
          <section
            className="relative p-3 border border-cyber-tertiary/50"
            style={{
              background: "rgba(0, 255, 136, 0.04)",
              clipPath:
                "polygon(0 4px, 4px 0, calc(100% - 4px) 0, 100% 4px, 100% calc(100% - 4px), calc(100% - 4px) 100%, 4px 100%, 0 calc(100% - 4px))",
              boxShadow: "inset 0 0 16px rgba(0, 255, 136, 0.06)",
            }}
          >
            <div
              className="font-hud text-[10px] tracking-[0.3em] uppercase text-cyber-tertiary mb-1.5"
              style={{ textShadow: "0 0 6px rgba(0, 255, 136, 0.5)" }}
            >
              ◈ Why this matters
            </div>
            <p className="text-sm font-mono text-cyber-text leading-relaxed">
              {rationale}
            </p>
          </section>

          {excerpt && entity && (
            <section>
              <div className="font-hud text-[10px] tracking-[0.3em] uppercase text-cyber-textDim mb-1.5">
                // Excerpt
              </div>
              <blockquote
                className="text-sm font-mono text-cyber-text leading-relaxed pl-3 italic"
                style={{
                  borderLeft: "2px solid #00d4ff",
                  boxShadow: "-2px 0 8px rgba(0, 212, 255, 0.2)",
                }}
              >
                {highlightName(excerpt, entity.name)}
              </blockquote>
            </section>
          )}

          {relationships.length > 0 && (
            <section>
              <div className="font-hud text-[10px] tracking-[0.3em] uppercase text-cyber-textDim mb-1.5">
                // Relationships from this source
              </div>
              <ul className="space-y-1.5">
                {relationships.map((r) => {
                  const fromName = nodes.get(r.fromId)?.name ?? r.fromId;
                  const toName = nodes.get(r.toId)?.name ?? r.toId;
                  return (
                    <li
                      key={r.id}
                      className="text-sm font-mono bg-cyber-panelAlt border border-cyber-border p-2"
                      style={{
                        clipPath:
                          "polygon(0 3px, 3px 0, calc(100% - 3px) 0, 100% 3px, 100% calc(100% - 3px), calc(100% - 3px) 100%, 3px 100%, 0 calc(100% - 3px))",
                      }}
                    >
                      <span className="text-cyber-text font-medium">
                        {fromName}
                      </span>
                      <span className="text-cyber-accent mx-1.5">
                        ─{r.predicate}→
                      </span>
                      <span className="text-cyber-text font-medium">
                        {toName}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          <a
            href={url}
            target="_blank"
            rel="noreferrer noopener"
            className="btn btn-primary w-full justify-center"
          >
            ↗ Open original
          </a>
        </div>
      </div>
    </div>
  );
}

/**
 * Bold every case-insensitive occurrence of `name` inside `text`.
 * Also bolds any aliased token the agent normalized (e.g. "TSMC" /
 * "Taiwan Semiconductor").
 *
 * Returns a ReactNode array so the caller can drop it straight into JSX.
 */
function highlightName(text: string, name: string): React.ReactNode {
  if (!name) return text;
  const needles = uniqueNeedles(name);
  if (needles.length === 0) return text;

  // Build one regex that matches any needle, longest first so "NVIDIA Corporation"
  // beats "NVIDIA" on overlap. Capturing group keeps matched tokens in `split`.
  const escaped = needles.sort((a, b) => b.length - a.length).map(escapeRegex);
  const pattern = `(${escaped.join("|")})`;
  const splitter = new RegExp(pattern, "gi");
  const matcher = new RegExp(`^${pattern}$`, "i"); // stateless test per part

  const parts = text.split(splitter);
  return parts.map((part, i) =>
    matcher.test(part) ? (
      <mark
        key={i}
        className="text-cyber-accent not-italic font-semibold px-0.5"
        style={{
          background: "rgba(0, 212, 255, 0.12)",
          textShadow: "0 0 6px rgba(0, 212, 255, 0.6)",
        }}
      >
        {part}
      </mark>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

function uniqueNeedles(name: string): string[] {
  const out = new Set<string>();
  const base = name.trim();
  if (base.length >= 2) out.add(base);
  // Also add the first token for multi-word names, so "Morris Chang" still
  // highlights just "Chang" elsewhere in the excerpt.
  const first = base.split(/\s+/)[0];
  if (first && first.length >= 3 && first !== base) out.add(first);
  return Array.from(out);
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
