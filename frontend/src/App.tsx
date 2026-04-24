import { HomeLanding } from "./components/HomeLanding";
import { SessionCockpit } from "./components/SessionCockpit";
import { useNexusStore } from "./store/nexus";

export function App() {
  const session = useNexusStore((s) => s.session);
  const setSession = useNexusStore((s) => s.setSession);
  const clearGraph = useNexusStore((s) => s.clearGraph);

  const reset = () => {
    clearGraph();
    setSession(null);
  };

  if (!session) {
    return <HomeLanding onStarted={setSession} />;
  }

  return <SessionCockpit onReset={reset} />;
}
