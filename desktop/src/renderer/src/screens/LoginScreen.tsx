import * as React from "react";
import { useAuth } from "../lib/auth";
import { Mascot } from "../components/Mascot";
import { GlowBackdrop } from "../components/GlowBackdrop";
import { FormField } from "../components/FormField";
import { Titlebar } from "../components/Titlebar";
import { EyeIcon, EyeOffIcon, LockIcon, ServerIcon, UserIcon } from "../icons";

export function LoginScreen() {
  const { login } = useAuth();
  const [serverUrl, setServerUrl] = React.useState("");
  const [username, setUsername] = React.useState("admin");
  const [password, setPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const canSubmit =
    serverUrl.trim().length > 4 && username.trim().length > 0 && password.length > 0 && !isSubmitting;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await login(serverUrl, username.trim(), password);
      if (!result.ok) {
        setError(result.message ?? "Coś poszło nie tak. Spróbuj ponownie.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex h-screen flex-col bg-background">
      <Titlebar />
      <div className="relative flex flex-1 items-center justify-center overflow-hidden">
        <form
          onSubmit={handleSubmit}
          className="relative flex w-full max-w-[340px] flex-col items-center px-8 text-center"
        >
          <div className="relative mb-3 flex items-center justify-center">
            <GlowBackdrop />
            <Mascot size={92} />
          </div>
          <div className="mb-4 text-[12px] font-extrabold tracking-[0.3em] text-text">ORDLY</div>
          <h1 className="text-title1 !text-[22px] !leading-[28px]">Witaj z powrotem</h1>
          <p className="mb-6 mt-1 max-w-[260px] text-footnote text-text-secondary">
            Twój sklep czekał. Połącz się ze swoim ORDLY na Raspberry Pi.
          </p>

          <div className="flex w-full flex-col gap-2 text-left">
            <FormField
              label="Adres serwera"
              icon={<ServerIcon className="shrink-0 text-primary" />}
              value={serverUrl}
              onChange={(e) => setServerUrl(e.target.value)}
              placeholder="https://cewastack2.tail7f5a20.ts.net"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              error={Boolean(error)}
            />
            <FormField
              label="Login"
              icon={<UserIcon className="shrink-0 text-text-secondary" />}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              error={Boolean(error)}
            />
            <FormField
              label="Hasło"
              icon={<LockIcon className="shrink-0 text-text-secondary" />}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="domyślnie: admin"
              type={showPassword ? "text" : "password"}
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              error={Boolean(error)}
              trailing={
                showPassword ? (
                  <EyeOffIcon className="text-text-secondary" />
                ) : (
                  <EyeIcon className="text-text-secondary" />
                )
              }
              onTrailingClick={() => setShowPassword((v) => !v)}
            />
          </div>

          {error ? <p className="mt-3 self-stretch text-caption leading-[17px] text-danger">{error}</p> : null}

          <button type="submit" disabled={!canSubmit} className="ordly-cta mt-4 w-full">
            {isSubmitting ? "Łączenie…" : "Połącz z ORDLY"}
          </button>

          {!isSubmitting && (
            <p className="mt-3 max-w-[280px] text-[11.5px] leading-4 text-text-dim">
              Domyślne dane logowania to <span className="font-bold text-text-secondary">admin</span> /{" "}
              <span className="font-bold text-text-secondary">admin</span> — zmień je w pliku .env po
              pierwszym uruchomieniu.
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
