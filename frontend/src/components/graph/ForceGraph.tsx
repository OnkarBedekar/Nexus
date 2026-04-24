import { useEffect, useMemo, useRef } from "react";
import * as d3 from "d3";
import type { Entity, Relationship } from "../../types/schema";
import { NODE_COLOR, nodeRadius } from "./colors";

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  entity: Entity;
  radius: number;
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  id: string;
  relationship: Relationship;
  source: string | SimNode;
  target: string | SimNode;
}

interface ForceGraphProps {
  nodes: Map<string, Entity>;
  edges: Map<string, Relationship>;
  selectedNodeId: string | null;
  activeUrl: string | null;
  onNodeSelect: (entity: Entity | null) => void;
}

// How long after an entity appears we keep highlighting it as "new".
const GLOW_MS = 3500;

// Opacity floor so even 0-confidence nodes stay readable.
const MIN_NODE_OPACITY = 0.35;

/**
 * D3 force-directed graph, React-owned-DOM.
 *
 * The simulation is initialized once on mount and mutated on every render via
 * `sim.nodes(...)` + `sim.force('link').links(...)` + `sim.alpha(0.3).restart()`.
 *
 * Per-tick positional updates bypass React's reconciler via `requestAnimationFrame`
 * - React owns element creation, D3 owns `cx/cy/x1/x2/y1/y2`.
 *
 * Visual polish this component implements:
 *   - Entrance glow: newly-added nodes get a filter ring that fades over GLOW_MS.
 *   - Confidence fade: node opacity scales linearly with confidence.
 *   - Active-branch emphasis: when the agent is browsing a URL, nodes whose
 *     sources include that URL stay fully opaque; everything else dims to ~55%.
 *   - Edge draw-in: on arrival each edge animates `stroke-dashoffset` from
 *     full length down to 0, giving the "snap into place" feeling.
 */
export function ForceGraph({
  nodes,
  edges,
  selectedNodeId,
  activeUrl,
  onNodeSelect,
}: ForceGraphProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const simRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null);
  const simNodesRef = useRef<Map<string, SimNode>>(new Map());
  const simLinksRef = useRef<SimLink[]>([]);
  const rafRef = useRef<number | null>(null);
  const sizeRef = useRef({ w: 800, h: 600 });

  // Track when each node/edge first appeared so we can fade out the "new" glow.
  const firstRenderedAtRef = useRef<Map<string, number>>(new Map());
  const edgeFirstRenderedAtRef = useRef<Map<string, number>>(new Map());

  // Init sim once.
  useEffect(() => {
    const sim = d3
      .forceSimulation<SimNode, SimLink>([])
      .force(
        "link",
        d3
          .forceLink<SimNode, SimLink>([])
          .id((d) => d.id)
          .distance(80)
          .strength(0.4),
      )
      .force("charge", d3.forceManyBody().strength(-180))
      .force("center", d3.forceCenter(sizeRef.current.w / 2, sizeRef.current.h / 2))
      .force("collide", d3.forceCollide<SimNode>().radius((d) => d.radius + 6))
      .alphaDecay(0.02);

    sim.on("tick", () => {
      if (rafRef.current != null) return;
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        const svg = svgRef.current;
        if (!svg) return;

        const nodeSel = svg.querySelectorAll<SVGGElement>("g.node");
        nodeSel.forEach((g) => {
          const id = g.dataset.id!;
          const n = simNodesRef.current.get(id);
          if (n && n.x != null && n.y != null) {
            g.setAttribute("transform", `translate(${n.x},${n.y})`);
          }
        });

        const linkSel = svg.querySelectorAll<SVGLineElement>("line.link");
        linkSel.forEach((line) => {
          const id = line.dataset.id!;
          const link = simLinksRef.current.find((l) => l.id === id);
          if (!link) return;
          const s = link.source as SimNode;
          const t = link.target as SimNode;
          if (s?.x != null && s.y != null && t?.x != null && t.y != null) {
            const dx = t.x - s.x;
            const dy = t.y - s.y;
            const dist = Math.hypot(dx, dy) || 1;
            const ux = dx / dist;
            const uy = dy / dist;
            const sourcePad = (s.radius ?? 0) + 2;
            const targetPad = (t.radius ?? 0) + 8;
            const x1 = s.x + ux * sourcePad;
            const y1 = s.y + uy * sourcePad;
            const x2 = t.x - ux * targetPad;
            const y2 = t.y - uy * targetPad;
            line.setAttribute("x1", String(x1));
            line.setAttribute("y1", String(y1));
            line.setAttribute("x2", String(x2));
            line.setAttribute("y2", String(y2));
          }
        });
      });
    });

    simRef.current = sim;

    return () => {
      sim.stop();
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  // Observe size.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        const { width, height } = e.contentRect;
        sizeRef.current = { w: width, h: height };
        const sim = simRef.current;
        if (sim) {
          const center = sim.force<d3.ForceCenter<SimNode>>("center");
          center?.x(width / 2).y(height / 2);
          sim.alpha(0.2).restart();
        }
      }
    });
    ro.observe(svg);
    return () => ro.disconnect();
  }, []);

  // Sync sim nodes/links when props change.
  useEffect(() => {
    const sim = simRef.current;
    if (!sim) return;

    const map = simNodesRef.current;
    const now = performance.now();

    // Upsert nodes, preserving x/y to avoid jumpiness.
    for (const [id, entity] of nodes) {
      const radius = nodeRadius(entity.claims.length);
      const existing = map.get(id);
      if (existing) {
        existing.entity = entity;
        existing.radius = radius;
      } else {
        map.set(id, {
          id,
          entity,
          radius,
          // Seed near the center with a small jitter so springs engage.
          x: sizeRef.current.w / 2 + (Math.random() - 0.5) * 40,
          y: sizeRef.current.h / 2 + (Math.random() - 0.5) * 40,
        });
        firstRenderedAtRef.current.set(id, now);
      }
    }
    // Drop removed nodes (rare, only on graph reset).
    for (const id of Array.from(map.keys())) {
      if (!nodes.has(id)) {
        map.delete(id);
        firstRenderedAtRef.current.delete(id);
      }
    }

    // Links: must reference live SimNode objects by id string so D3's
    // `forceLink.id` resolves them.
    const links: SimLink[] = [];
    for (const [id, rel] of edges) {
      if (!map.has(rel.fromId) || !map.has(rel.toId)) continue;
      links.push({
        id,
        relationship: rel,
        source: rel.fromId,
        target: rel.toId,
      });
      if (!edgeFirstRenderedAtRef.current.has(id)) {
        edgeFirstRenderedAtRef.current.set(id, now);
      }
    }
    for (const id of Array.from(edgeFirstRenderedAtRef.current.keys())) {
      if (!edges.has(id)) edgeFirstRenderedAtRef.current.delete(id);
    }
    simLinksRef.current = links;

    sim.nodes(Array.from(map.values()));
    const linkForce = sim.force<d3.ForceLink<SimNode, SimLink>>("link");
    linkForce?.links(links);
    sim.alpha(0.35).restart();
  }, [nodes, edges]);

  // --- Render ---
  const nodeList = useMemo(() => Array.from(nodes.values()), [nodes]);
  const edgeList = useMemo(
    () =>
      Array.from(edges.values()).filter(
        (e) => nodes.has(e.fromId) && nodes.has(e.toId),
      ),
    [edges, nodes],
  );

  // Compute which nodes are on the "active crawl branch".
  const activeNodeIds = useMemo(() => {
    if (!activeUrl) return null;
    const s = new Set<string>();
    for (const n of nodes.values()) {
      if (n.sources.some((src) => src.url === activeUrl)) {
        s.add(n.id);
      }
    }
    return s.size > 0 ? s : null;
  }, [activeUrl, nodes]);

  return (
    <svg
      ref={svgRef}
      className="w-full h-full block"
      role="img"
      aria-label="Knowledge graph"
    >
      <defs>
        <marker
          id="arrow"
          viewBox="0 -4 8 8"
          refX="8"
          refY="0"
          markerWidth="7"
          markerHeight="7"
          orient="auto"
        >
          <path d="M0,-4L8,0L0,4Z" fill="#9fb2d0" opacity="0.9" />
        </marker>
        {/* Entrance glow filter — stacked blurs deliver the "neon sign bloom"
            look. stdDeviation larger than before so nodes *really* glow. */}
        <filter id="node-glow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        {/* Soft persistent glow that every live node gets. Tuned so it's
            visible but not distracting when 50+ nodes are on screen. */}
        <filter
          id="node-soft-glow"
          x="-50%"
          y="-50%"
          width="200%"
          height="200%"
        >
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        {/* Tech-grid backdrop rendered inside the SVG so it pans with zoom
            if we ever add zoom. 50px grid lines in accent cyan at 3% alpha. */}
        <pattern
          id="cyber-grid"
          x="0"
          y="0"
          width="50"
          height="50"
          patternUnits="userSpaceOnUse"
        >
          <path
            d="M 50 0 L 0 0 0 50"
            fill="none"
            stroke="#00d4ff"
            strokeOpacity="0.05"
            strokeWidth="1"
          />
        </pattern>
        {/* Scanline overlay pattern — same as the CSS body overlay but
            applied to the graph surface for doubled CRT density. */}
        <pattern
          id="cyber-scanlines"
          x="0"
          y="0"
          width="4"
          height="4"
          patternUnits="userSpaceOnUse"
        >
          <rect width="4" height="2" fill="rgba(0,0,0,0.22)" />
        </pattern>
      </defs>

      {/* Background layers — grid then scanlines. Pointer-events none so
          they never swallow node clicks. */}
      <rect
        width="100%"
        height="100%"
        fill="url(#cyber-grid)"
        pointerEvents="none"
      />

      <g className="links">
        {edgeList.map((e) => {
          const fromNode = nodes.get(e.fromId)!;
          const color = NODE_COLOR[fromNode.type];
          const opacity = activeNodeIds
            ? activeNodeIds.has(e.fromId) || activeNodeIds.has(e.toId)
              ? 0.75
              : 0.18
            : e.confidence >= 0.6
              ? 0.55
              : 0.3;
          const isNew =
            performance.now() - (edgeFirstRenderedAtRef.current.get(e.id) ?? 0) <
            GLOW_MS;
          // Long dash length so `stroke-dasharray` renders a "draw-in" from 200
          // down to 0 via <animate>.
          return (
            <line
              key={e.id}
              className="link"
              data-id={e.id}
              stroke={color}
              strokeOpacity={opacity}
              // Slightly thicker than before so the neon-painted lines read
              // as signal paths rather than hairline ticks.
              strokeWidth={e.confidence >= 0.6 ? 1.4 : 0.8}
              markerEnd="url(#arrow)"
              strokeDasharray={isNew ? "200" : undefined}
              style={{
                filter: `drop-shadow(0 0 2px ${color}99)`,
                transition: "stroke-opacity 250ms ease",
              }}
            >
              {isNew && (
                <animate
                  attributeName="stroke-dashoffset"
                  from="200"
                  to="0"
                  dur="0.55s"
                  fill="freeze"
                />
              )}
            </line>
          );
        })}
      </g>

      <g className="nodes">
        {nodeList.map((n) => {
          const r = nodeRadius(n.claims.length);
          const selected = n.id === selectedNodeId;
          const color = NODE_COLOR[n.type];

          const firstAt = firstRenderedAtRef.current.get(n.id) ?? 0;
          const age = performance.now() - firstAt;
          const isNew = age < GLOW_MS;
          const isActive = activeNodeIds?.has(n.id) ?? false;

          // Confidence fade, with a bump when on the active branch.
          let opacity =
            MIN_NODE_OPACITY + (1 - MIN_NODE_OPACITY) * clamp01(n.confidence);
          if (activeNodeIds && !isActive && !selected) {
            opacity = Math.min(opacity, 0.55);
          }

          return (
            <g
              key={n.id}
              className="node cursor-pointer"
              data-id={n.id}
              opacity={opacity}
              onClick={(e) => {
                e.stopPropagation();
                onNodeSelect(selected ? null : n);
              }}
              style={{ transition: "opacity 400ms" }}
            >
              {/* Entrance bloom — a neon-green flash that expands and fades
                  to emphasize the moment an entity comes online. */}
              {isNew && (
                <circle
                  r={r + 10}
                  fill={color}
                  opacity={0.0}
                  filter="url(#node-glow)"
                >
                  <animate
                    attributeName="opacity"
                    from="0.85"
                    to="0"
                    dur="1.6s"
                    fill="freeze"
                  />
                  <animate
                    attributeName="r"
                    from={r}
                    to={r + 22}
                    dur="1.6s"
                    fill="freeze"
                  />
                </circle>
              )}
              {/* Active-branch HUD ring — outer sweep ring + inner pulse ring
                  signal that the agent is actively on this source. */}
              {isActive && !selected && (
                <>
                  <circle
                    r={r + 6}
                    fill="none"
                    stroke="#00d4ff"
                    strokeOpacity={0.55}
                    strokeWidth={1}
                    strokeDasharray="4 3"
                    style={{ filter: "drop-shadow(0 0 4px #00d4ff)" }}
                  >
                    <animateTransform
                      attributeName="transform"
                      type="rotate"
                      from="0"
                      to="360"
                      dur="6s"
                      repeatCount="indefinite"
                    />
                  </circle>
                  <circle
                    r={r + 2}
                    fill="none"
                    stroke={color}
                    strokeOpacity={0.9}
                    strokeWidth={1.5}
                    style={{ filter: `drop-shadow(0 0 4px ${color})` }}
                  >
                    <animate
                      attributeName="r"
                      values={`${r + 2};${r + 10};${r + 2}`}
                      dur="1.8s"
                      repeatCount="indefinite"
                    />
                    <animate
                      attributeName="stroke-opacity"
                      values="0.9;0.1;0.9"
                      dur="1.8s"
                      repeatCount="indefinite"
                    />
                  </circle>
                </>
              )}
              {selected && (
                <>
                  {/* Corner-bracket-style selection ring — renders as a
                      rotating square outline to feel HUD-like. */}
                  <circle
                    r={r + 8}
                    fill="none"
                    stroke="#00d4ff"
                    strokeWidth={1}
                    strokeOpacity={0.6}
                    strokeDasharray="6 4"
                    style={{ filter: "drop-shadow(0 0 6px #00d4ff)" }}
                  >
                    <animateTransform
                      attributeName="transform"
                      type="rotate"
                      from="0"
                      to="360"
                      dur="10s"
                      repeatCount="indefinite"
                    />
                  </circle>
                  <circle
                    r={r + 4}
                    fill="none"
                    stroke="#00d4ff"
                    strokeWidth={1.5}
                    opacity={0.95}
                  />
                </>
              )}
              <circle
                r={r}
                fill={color}
                stroke={selected ? "#00d4ff" : color}
                strokeWidth={selected ? 2 : 1}
                opacity={0.95}
                style={{
                  filter: `drop-shadow(0 0 4px ${color}) drop-shadow(0 0 10px ${color}66)`,
                }}
              >
                <animate
                  attributeName="r"
                  from={0}
                  to={r}
                  dur="0.4s"
                  begin="0s"
                  fill="freeze"
                />
              </circle>
              {r > 16 && (
                <text
                  y={r + 14}
                  textAnchor="middle"
                  fontSize={10.5}
                  fontFamily='"Share Tech Mono", "JetBrains Mono", monospace'
                  fill="#e4e9f2"
                  style={{
                    pointerEvents: "none",
                    letterSpacing: "0.15em",
                    textShadow: "0 0 4px rgba(0,0,0,0.85)",
                    textTransform: "uppercase",
                  }}
                >
                  {n.name.length > 22 ? n.name.slice(0, 21) + "…" : n.name}
                </text>
              )}
            </g>
          );
        })}
      </g>
    </svg>
  );
}

function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x));
}
