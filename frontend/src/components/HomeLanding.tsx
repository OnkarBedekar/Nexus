import { useEffect, useState } from "react";
import { startSession } from "../api/rest";
import type { ResearchSession } from "../types/schema";

const DEMO_TOPICS = [
  "AI chip supply chain",
  "Quantum computing",
  "Carbon capture",
];

// Subtitle typed in at session-start to sell the terminal aesthetic.
const SUBTITLE =
  "Watch an autonomous web agent search the open web and assemble a knowledge graph in real time.";

interface Props {
  onStarted: (s: ResearchSession) => void;
}

export function HomeLanding({ onStarted }: Props) {
  const [topic, setTopic] = useState("AI chip supply chain");
  const [seedUrl, setSeedUrl] = useState(
    "https://medium.com/@gaetanlion/the-ai-chips-supply-chain-incredible-fragility-6d6a7197b3c5",
  );
  const [useTwoPhase, setUseTwoPhase] = useState(true);
  const [maxDiscoverUrls, setMaxDiscoverUrls] = useState(12);
  const [collaborators, setCollaborators] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const typed = useTypewriter(SUBTITLE, 22);

  async function go() {
    if (!topic.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const session = await startSession({
        topic: topic.trim(),
        seedUrl: seedUrl.trim() || undefined,
        collaborators: collaborators
          .split(",")
          .map((name) => name.trim())
          .filter(Boolean),
        useTwoPhase,
        maxDiscoverUrls,
      });
      onStarted(session);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative h-full w-full overflow-hidden bg-nexus-bg flex items-center justify-center p-6">
      {/* Background layers — cyber grid + corner gradient mesh. */}
      <div
        className="absolute inset-0 cyber-grid-bg pointer-events-none"
        aria-hidden
      />
      <div
        className="absolute inset-0 pointer-events-none"
        aria-hidden
        style={{
          backgroundImage:
            "radial-gradient(ellipse 60% 50% at 10% 0%, rgba(0, 212, 255, 0.12), transparent 60%), radial-gradient(ellipse 60% 50% at 90% 100%, rgba(255, 0, 255, 0.08), transparent 60%)",
        }}
      />

      <div className="relative w-full max-w-5xl grid lg:grid-cols-[1.1fr_1fr] gap-8 items-center z-10">
        {/* ------------------------------------------------------------------
            LEFT: Hero with glitched NEXUS title. This is the "moment".
            ------------------------------------------------------------------ */}
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <span className="chip text-cyber-accent border-cyber-accent/40 bg-cyber-accent/5">
              <span
                className="w-1.5 h-1.5 rounded-full bg-cyber-tertiary"
                style={{ boxShadow: "0 0 6px #00ff88" }}
              />
              System online
            </span>
            <span className="font-hud text-[10.5px] tracking-[0.25em] text-cyber-textDim uppercase">
              //  research cockpit  v0.1
            </span>
          </div>

          <h1
            className="cyber-glitch font-display font-black leading-none"
            data-text="NEXUS"
            style={{
              fontSize: "clamp(4rem, 12vw, 9rem)",
              letterSpacing: "0.08em",
              color: "#e4e9f2",
            }}
          >
            NEXUS
          </h1>

          <div className="space-y-3">
            <div className="font-hud text-[10.5px] tracking-[0.25em] text-cyber-textDim uppercase">
              Mission brief
            </div>
            <p
              className="font-mono text-base md:text-lg text-cyber-text leading-relaxed min-h-[3.2em]"
              aria-label={SUBTITLE}
            >
              {typed}
              <span
                className="inline-block w-[0.55em] h-[1em] align-[-0.12em] ml-0.5 bg-cyber-accent animate-blink"
                style={{ boxShadow: "0 0 8px #00d4ff" }}
                aria-hidden
              />
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-2">
            <span className="font-hud text-[10.5px] tracking-[0.25em] text-cyber-textDim uppercase">
              Integrations
            </span>
            <span className="text-cyber-border">::</span>
            {["TinyFish", "Cosmo Router", "Redis"].map((name) => (
              <span
                key={name}
                className="chip text-cyber-textDim border-cyber-border"
              >
                {name}
              </span>
            ))}
          </div>
        </div>

        {/* ------------------------------------------------------------------
            RIGHT: Terminal-styled session form.
            ------------------------------------------------------------------ */}
        <div className="panel relative p-6 md:p-7 space-y-5 bg-cyber-panel">
          {/* Terminal window chrome — traffic lights + path crumb. */}
          <div className="flex items-center justify-between pb-3 border-b border-cyber-border">
            <div className="flex items-center gap-3">
              <div className="cyber-traffic-lights" aria-hidden>
                <span />
                <span />
                <span />
              </div>
              <span className="font-hud text-[10.5px] tracking-[0.25em] text-cyber-textDim uppercase">
                nexus@cockpit ~/new_session
              </span>
            </div>
            <span
              className="chip text-cyber-tertiary border-cyber-tertiary/40"
              style={{ background: "rgba(0, 255, 136, 0.05)" }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full bg-cyber-tertiary animate-pulse"
                style={{ boxShadow: "0 0 6px #00ff88" }}
              />
              ready
            </span>
          </div>

          <Field label="Topic" required>
            <div className="cyber-input-wrap">
              <input
                className="cyber-input"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g. AI chip supply chain"
                onKeyDown={(e) => {
                  if (e.key === "Enter") go();
                }}
                autoFocus
              />
            </div>
          </Field>

          <div className="flex flex-wrap gap-1.5">
            <span className="font-hud text-[10px] tracking-[0.25em] text-cyber-textDim uppercase self-center mr-1">
              Quick-load
            </span>
            {DEMO_TOPICS.map((t) => (
              <button
                key={t}
                type="button"
                className="chip border-cyber-border text-cyber-textDim hover:text-cyber-accent hover:border-cyber-accent/60 transition"
                onClick={() => setTopic(t)}
              >
                {t}
              </button>
            ))}
          </div>

          <div className="flex flex-col sm:flex-row sm:items-end gap-3">
            <label className="flex items-center gap-2 cursor-pointer select-none text-sm font-mono text-cyber-text">
              <input
                type="checkbox"
                className="accent-cyber-accent w-3.5 h-3.5"
                checked={useTwoPhase}
                onChange={(e) => setUseTwoPhase(e.target.checked)}
              />
              <span>Two-phase: search sources first, then run agent on each (recommended)</span>
            </label>
            <div className="w-full sm:min-w-[5.5rem] sm:w-44">
              <Field label="Max source URLs">
                <div className="cyber-input-wrap cyber-input-wrap--tight">
                  <input
                    type="number"
                    className="cyber-input tabular-nums"
                    min={1}
                    max={25}
                    value={maxDiscoverUrls}
                    disabled={!useTwoPhase}
                    onChange={(e) =>
                      setMaxDiscoverUrls(
                        Math.min(25, Math.max(1, parseInt(e.target.value, 10) || 12)),
                      )
                    }
                  />
                </div>
              </Field>
            </div>
          </div>

          <Field label="Seed URL (optional)">
            <div className="cyber-input-wrap">
              <input
                className="cyber-input"
                value={seedUrl}
                onChange={(e) => setSeedUrl(e.target.value)}
                placeholder="fallback when discovery returns nothing, or full legacy run when two-phase is off"
              />
            </div>
          </Field>

          <Field label="Collaborators (optional, comma-separated)">
            <div className="cyber-input-wrap">
              <input
                className="cyber-input"
                value={collaborators}
                onChange={(e) => setCollaborators(e.target.value)}
                placeholder="alice, advisor-bob"
              />
            </div>
          </Field>

          <div className="flex items-center justify-between gap-3 pt-2">
            <span className="font-hud text-[10px] tracking-[0.25em] text-cyber-textDim uppercase">
              {loading ? "injecting..." : "awaiting input"}
            </span>
            <button
              type="button"
              onClick={go}
              disabled={loading || !topic.trim()}
              className="btn btn-primary"
            >
              {loading ? "▮ Starting..." : "▶ Start research"}
            </button>
          </div>

          {error && (
            <div
              className="relative text-sm font-mono text-cyber-danger border p-3"
              style={{
                borderColor: "#ff336680",
                background: "rgba(255, 51, 102, 0.05)",
                boxShadow: "inset 0 0 12px rgba(255, 51, 102, 0.08)",
              }}
            >
              <span className="font-hud text-[10px] tracking-[0.25em] uppercase text-cyber-danger">
                ⚠ System fault ::
              </span>
              <div className="mt-1 text-cyber-text">{error}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Field wrapper — label rendered as HUD-style uppercase caption. */
function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="font-hud text-[10.5px] tracking-[0.25em] text-cyber-textDim uppercase flex items-center gap-1.5">
        <span className="text-cyber-accent">❯</span>
        {label}
        {required && <span className="text-cyber-secondary">*</span>}
      </span>
      {children}
    </label>
  );
}

/**
 * Tiny typewriter that reveals `text` one character at a time. Used on the
 * hero subtitle to sell the "connection is being established" vibe.
 * Skipped during reduced-motion (returns full text immediately).
 */
function useTypewriter(text: string, msPerChar: number): string {
  const [out, setOut] = useState("");
  useEffect(() => {
    if (
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
    ) {
      setOut(text);
      return;
    }
    setOut("");
    let i = 0;
    const id = window.setInterval(() => {
      i += 1;
      setOut(text.slice(0, i));
      if (i >= text.length) window.clearInterval(id);
    }, msPerChar);
    return () => window.clearInterval(id);
  }, [text, msPerChar]);
  return out;
}
