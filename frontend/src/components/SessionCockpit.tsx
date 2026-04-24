import { useSessionSubscriptions } from "../hooks/useSessionSubscriptions";
import { useNexusStore } from "../store/nexus";
import { BottomBar } from "./layout/BottomBar";
import { Header } from "./layout/Header";
import { AgentPanel } from "./panels/AgentPanel";
import { GraphPanel } from "./panels/GraphPanel";
import { NodeDetailPanel } from "./panels/NodeDetailPanel";
import { SourcePreviewDrawer } from "./panels/SourcePreviewDrawer";
import { LivePreviewModal } from "./panels/LivePreviewModal";

interface Props {
  onReset: () => void;
}

export function SessionCockpit({ onReset }: Props) {
  const session = useNexusStore((s) => s.session);
  const setPreviewExpanded = useNexusStore((s) => s.setPreviewExpanded);

  useSessionSubscriptions(session?.id ?? null);

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-cyber-void relative">
      {/* Subtle cyber-grid on the root so gaps between panels don't look
          empty. The scanline overlay is applied globally via body::before. */}
      <div
        className="absolute inset-0 cyber-grid-bg pointer-events-none opacity-60"
        aria-hidden
      />
      <Header onOpenPreview={() => setPreviewExpanded(true)} onReset={onReset} />
      <main className="flex-1 min-h-0 relative">
        <div className="absolute inset-0 grid gap-2 p-2 grid-cols-[280px_1fr_340px] grid-rows-1">
          <AgentPanel />
          <GraphPanel />
          <NodeDetailPanel />
        </div>
        <LivePreviewModal />
        <SourcePreviewDrawer />
      </main>
      <BottomBar />
    </div>
  );
}
