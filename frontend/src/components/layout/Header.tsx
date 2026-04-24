import { useNexusStore } from "../../store/nexus";

interface HeaderProps {
  onOpenPreview: () => void;
  onReset: () => void;
}

export function Header({ onOpenPreview, onReset }: HeaderProps) {
  const session = useNexusStore((s) => s.session);
  const agent = useNexusStore((s) => s.agentStatus);
  const requestFinalReport = useNexusStore((s) => s.requestFinalReport);
  const canGenerateReport = Boolean(session && (agent?.state === "done" || session.status === "complete"));

  return (
    <header className="relative flex items-center justify-between gap-4 px-5 py-3 bg-nexus-surface border-b border-nexus-border overflow-hidden">
      {/* Thin top scanline + bottom gradient accent to give the header a
          physical "illuminated bar" feel. */}
      <div
        className="absolute inset-x-0 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent, #00d4ff 50%, transparent)",
          opacity: 0.5,
        }}
      />
      <div
        className="absolute inset-x-0 bottom-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent, #1f1f33 50%, transparent)",
        }}
      />

      <div className="flex items-center gap-5 min-w-0">
        {/* NEXUS wordmark with a subtle occasional glitch flicker. The
            `data-text` drives the ::before / ::after chromatic layers. */}
        <div className="flex items-center gap-2.5">
          <span
            className="relative inline-block text-cyber-accent"
            style={{
              textShadow:
                "0 0 6px rgba(0, 212, 255, 0.7), 0 0 14px rgba(0, 212, 255, 0.35)",
            }}
          >
            <span className="font-display font-black text-lg tracking-[0.25em]">
              NEXUS
            </span>
          </span>
          <span className="chip border-cyber-border text-cyber-textDim px-1.5">
            v0.1
          </span>
        </div>

        <span className="text-cyber-border select-none" aria-hidden>
          ⧸⧸
        </span>

        {session ? (
          <div className="flex items-center gap-3 min-w-0">
            <span className="font-hud text-[10.5px] tracking-[0.25em] text-cyber-textDim uppercase">
              Topic ::
            </span>
            <span className="font-mono text-sm text-cyber-text truncate max-w-md">
              {session.topic}
            </span>
          </div>
        ) : (
          <span className="font-hud text-[10.5px] tracking-[0.25em] text-cyber-textDim uppercase">
            No active session
          </span>
        )}
      </div>

      <div className="flex items-center gap-2.5">
        {canGenerateReport ? (
          <button
            type="button"
            onClick={requestFinalReport}
            className="btn btn-primary"
          >
            Generate Final Report
          </button>
        ) : null}

        <button type="button" onClick={onOpenPreview} className="btn btn-primary">
          ⛶ Live preview
        </button>
        <button type="button" onClick={onReset} className="btn">
          + New session
        </button>
      </div>
    </header>
  );
}
