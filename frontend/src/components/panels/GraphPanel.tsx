import { useNexusStore } from "../../store/nexus";
import { ForceGraph } from "../graph/ForceGraph";

export function GraphPanel() {
  const selectedNodeId = useNexusStore((s) => s.selectedNodeId);
  const selectNode = useNexusStore((s) => s.selectNode);
  const agent = useNexusStore((s) => s.agentStatus);
  const nodes = useNexusStore((s) => s.nodes);
  const edges = useNexusStore((s) => s.edges);

  // The "active crawl branch" = nodes whose sources include the URL the agent
  // is currently on. The graph uses this to dim unrelated nodes so the user's
  // eye tracks where the new content is coming from.
  const activeUrl =
    agent?.state === "browsing" || agent?.state === "extracting"
      ? agent?.currentUrl ?? null
      : null;

  return (
    <section
      className="panel relative h-full overflow-hidden"
      onClick={() => selectNode(null)}
    >
      <ForceGraph
        nodes={nodes}
        edges={edges}
        selectedNodeId={selectedNodeId}
        activeUrl={activeUrl}
        onNodeSelect={(e) => selectNode(e?.id ?? null)}
      />
      {nodes.size === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center space-y-2">
            <div
              className="inline-flex items-center gap-2 font-hud text-[10.5px] tracking-[0.3em] uppercase text-cyber-accent"
              style={{ textShadow: "0 0 6px rgba(0, 212, 255, 0.5)" }}
            >
              <span
                className="w-1.5 h-1.5 bg-cyber-accent animate-pulse"
                style={{ boxShadow: "0 0 6px #00d4ff" }}
              />
              awaiting data stream
            </div>
            <div className="text-sm font-mono text-cyber-textDim">
              graph will render here as entities arrive
              <span
                className="inline-block w-1.5 h-3 bg-cyber-textDim animate-blink ml-1 align-middle"
                aria-hidden
              />
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
