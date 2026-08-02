import { useAuth } from "./lib/auth";
import { LoginScreen } from "./screens/LoginScreen";
import { ShellLayout } from "./screens/ShellLayout";

export function App() {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-footnote text-text-dim">
        Wczytywanie…
      </div>
    );
  }
  if (status === "unauthenticated") {
    return <LoginScreen />;
  }
  return <ShellLayout />;
}
