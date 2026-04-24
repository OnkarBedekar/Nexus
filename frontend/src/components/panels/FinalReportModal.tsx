import { useEffect, useMemo, useState } from "react";
import { getFinalReport } from "../../api/rest";
import { useNexusStore } from "../../store/nexus";
import type { FinalReportResponse } from "../../types/schema";

export function FinalReportModal() {
  const isOpen = useNexusStore((s) => s.isFinalReportOpen);
  const setOpen = useNexusStore((s) => s.setFinalReportOpen);
  const session = useNexusStore((s) => s.session);
  const [report, setReport] = useState<FinalReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !session?.id) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const next = await getFinalReport(session.id);
        if (!cancelled) setReport(next);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to fetch final report");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isOpen, session?.id]);

  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isOpen, setOpen]);

  const baseFileName = useMemo(() => {
    const topic = (report?.summary.topic || session?.topic || "nexus-report")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60);
    return topic || "nexus-report";
  }, [report?.summary.topic, session?.topic]);

  if (!isOpen) return null;

  return (
    <div
      className="absolute inset-0 z-40 bg-black/70 backdrop-blur-sm flex p-3"
      onClick={() => setOpen(false)}
    >
      <div
        className="panel panel-holo relative w-full h-full overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-2 border-b border-cyber-border bg-cyber-panelAlt/60">
          <div className="flex items-center gap-3 min-w-0">
            <span className="font-hud text-[10px] tracking-[0.25em] text-cyber-textDim uppercase">
              Final report
            </span>
            {report && (
              <span className="text-[11px] font-mono text-cyber-textDim truncate">
                {report.summary.paperCount} papers · {report.summary.sourceCount} sources
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn !px-2 !py-1 text-[10px]"
              onClick={() => {
                if (!report?.markdown) return;
                navigator.clipboard.writeText(report.markdown).catch(() => {});
              }}
              disabled={!report?.markdown}
            >
              Copy
            </button>
            <button
              type="button"
              className="btn !px-2 !py-1 text-[10px]"
              onClick={() => {
                if (!report?.markdown) return;
                downloadTextFile(`${baseFileName}.md`, report.markdown, "text/markdown");
              }}
              disabled={!report?.markdown}
            >
              Download .md
            </button>
            <button
              type="button"
              className="btn !px-2 !py-1 text-[10px]"
              onClick={() => {
                if (!report) return;
                downloadTextFile(
                  `${baseFileName}.json`,
                  JSON.stringify(report, null, 2),
                  "application/json",
                );
              }}
              disabled={!report}
            >
              Download .json
            </button>
            <button type="button" className="btn" onClick={() => setOpen(false)}>
              ✕ Close
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {loading && (
            <div className="text-[11px] font-mono text-cyber-textDim">Generating final report...</div>
          )}
          {error && <div className="text-[11px] font-mono text-cyber-danger">{error}</div>}
          {!loading && !error && report?.isEmpty && (
            <div className="space-y-2 mb-3">
              <div className="font-hud text-[10px] tracking-[0.25em] text-cyber-warn uppercase">
                Report not ready
              </div>
              <div className="text-sm font-mono text-cyber-textDim">
                {report.emptyReason ||
                  "No normalized papers are available yet. Check that the normalizer worker is running."}
              </div>
            </div>
          )}
          {!loading && !error && report?.markdown && (
            <pre className="text-[11px] whitespace-pre-wrap font-mono text-cyber-text leading-relaxed bg-cyber-panelAlt border border-cyber-border p-2.5">
              {report.markdown}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

function downloadTextFile(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(href);
}
