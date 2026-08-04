/**
 * Logowanie - polaczenie z wlasnym Raspberry Pi przez Tailscale.
 *
 * Ekran uzywa tego samego systemu wizualnego co reszta aplikacji, ale
 * bez paska bocznego i topbara - do czasu polaczenia nie ma czego
 * pokazywac w nawigacji.
 */
import * as React from "react";
import { useAuth } from "../lib/auth";
import { Mascot } from "../components/Mascot";
import { Titlebar } from "../components/Titlebar";
import { Button } from "../components/ui";
import { EyeIcon, EyeOffIcon, LockIcon, ServerIcon, UserIcon } from "../icons";

const FIELD_CLASS =
  "flex items-center gap-2.5 rounded-md border border-line bg-panel-2 px-3.5 py-2.5 transition-colors focus-within:border-teal-bright";

function Field({
  label,
  icon,
  trailing,
  onTrailingClick,
  ...inputProps
}: {
  label: string;
  icon: React.ReactNode;
  trailing?: React.ReactNode;
  onTrailingClick?: () => void;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="o-eyebrow">{label}</span>
      <span className={FIELD_CLASS}>
        {icon}
        <input
          {...inputProps}
          className="min-w-0 flex-1 bg-transparent text-[13px] text-white outline-none placeholder:text-slate-dim"
        />
        {trailing && (
          <button
            type="button"
            onClick={onTrailingClick}
            aria-label="Pokaż lub ukryj hasło"
            className="shrink-0 text-slate-dim hover:text-white"
          >
            {trailing}
          </button>
        )}
      </span>
    </label>
  );
}

export function LoginScreen() {
  const { login } = useAuth();
  const [serverUrl, setServerUrl] = React.useState("");
  const [username, setUsername] = React.useState("admin");
  const [password, setPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const canSubmit =
    serverUrl.trim().length > 4 &&
    username.trim().length > 0 &&
    password.length > 0 &&
    !isSubmitting;

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
    <div className="flex h-screen flex-col bg-panel text-white">
      <Titlebar online={false} hostname="" />
      <div className="relative flex flex-1 items-center justify-center overflow-hidden">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -left-40 -top-40 h-[520px] w-[520px] rounded-full opacity-50 blur-[110px]"
          style={{ background: "rgba(62,170,175,.16)" }}
        />
        <form
          onSubmit={handleSubmit}
          className="relative flex w-full max-w-[360px] flex-col px-8"
        >
          <div className="mb-5 flex flex-col items-center text-center">
            <Mascot pose="orders" size={92} />
            <div className="o-display mt-3 text-[15.5px] font-semibold tracking-[-.015em]">
              ORDLY
            </div>
            <h1 className="o-hero-title mt-3">Witaj z powrotem</h1>
            <p className="mt-1.5 max-w-[280px] text-[12.5px] leading-[1.55] text-slate">
              Połącz się ze swoim ORDLY na Raspberry Pi.
            </p>
          </div>

          <div className="flex flex-col gap-3">
            <Field
              label="Adres serwera"
              icon={<ServerIcon size={15} className="shrink-0 text-teal-bright" />}
              value={serverUrl}
              onChange={(event) => setServerUrl(event.target.value)}
              placeholder="https://cewastack2.tail7f5a20.ts.net"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
            />
            <Field
              label="Login"
              icon={<UserIcon size={15} className="shrink-0 text-slate-dim" />}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="admin"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
            />
            <Field
              label="Hasło"
              icon={<LockIcon size={15} className="shrink-0 text-slate-dim" />}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type={showPassword ? "text" : "password"}
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              trailing={showPassword ? <EyeOffIcon size={15} /> : <EyeIcon size={15} />}
              onTrailingClick={() => setShowPassword((prev) => !prev)}
            />
          </div>

          {error && (
            <p className="mt-3 text-[11.5px] leading-[1.5] text-coral">{error}</p>
          )}

          <Button type="submit" disabled={!canSubmit} className="mt-4 !py-3">
            {isSubmitting ? "Łączę…" : "Połącz z ORDLY"}
          </Button>

          <p className="mt-3.5 text-center text-[11px] leading-[1.55] text-slate-dim">
            Adres musi zaczynać się od <b className="text-slate">https://</b> - Tailscale
            serwuje ORDLY po HTTPS na porcie 443.
          </p>
        </form>
      </div>
    </div>
  );
}
