import { useAuth } from "./lib/auth";
import { LoginScreen } from "./screens/LoginScreen";
import { ShellLayout } from "./screens/ShellLayout";
import { Mascot } from "./components/Mascot";

export function App() {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 bg-panel">
        <Mascot pose="idle" size={72} />
        <p className="text-[12.5px] text-slate-dim">Wczytywanie…</p>
      </div>
    );
  }
  if (status === "unauthenticated") {
    return <LoginScreen />;
  }
  return <ShellLayout />;
}
