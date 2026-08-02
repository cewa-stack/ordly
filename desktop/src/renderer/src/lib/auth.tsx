import * as React from "react";
import type { Session } from "../types/api";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface LoginOutcome {
  ok: boolean;
  status?: number;
  message?: string;
}

interface AuthContextValue {
  session: Session | null;
  status: AuthStatus;
  login: (baseUrl: string, username: string, password: string) => Promise<LoginOutcome>;
  logout: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = React.useState<Session | null>(null);
  const [status, setStatus] = React.useState<AuthStatus>("loading");

  React.useEffect(() => {
    let cancelled = false;
    window.ordly.auth.getSession().then((existing) => {
      if (cancelled) return;
      setSession(existing);
      setStatus(existing ? "authenticated" : "unauthenticated");
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = React.useCallback(
    async (baseUrl: string, username: string, password: string): Promise<LoginOutcome> => {
      const result = await window.ordly.auth.login(baseUrl, username, password);
      if (result.ok) {
        setSession(result.data);
        setStatus("authenticated");
        return { ok: true };
      }
      return { ok: false, status: result.status, message: result.message };
    },
    []
  );

  const logout = React.useCallback(async () => {
    await window.ordly.auth.logout();
    setSession(null);
    setStatus("unauthenticated");
  }, []);

  const value = React.useMemo(
    () => ({ session, status, login, logout }),
    [session, status, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth musi być użyty wewnątrz AuthProvider");
  }
  return ctx;
}
