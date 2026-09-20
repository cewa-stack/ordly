import { useAuth } from "./lib/auth";
import { LoginScreen } from "./screens/LoginScreen";
import { ShellLayout } from "./screens/ShellLayout";
import { Ordlak } from "./components/Ordlak";

export function App() {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3">
        {/* Wczytywanie to praca, nie spoczynek - stad `sync`, nie `idle`. */}
        <Ordlak state="sync" size={72} />
        <p className="o-mono text-[10.5px] uppercase tracking-[.15em] text-text-3">
          Wczytywanie…
        </p>
      </div>
    );
  }
  if (status === "unauthenticated") {
    return <LoginScreen />;
  }
  return <ShellLayout />;
}
