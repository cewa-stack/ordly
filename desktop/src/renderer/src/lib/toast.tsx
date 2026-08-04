/**
 * Toasty wg sekcji 5 i 7.3 specyfikacji: prawy dolny rog, Ordi 30 px,
 * tytul + podtytul, 2600 ms zycia, 320 ms wyjscia w prawo.
 *
 * Reguly tresci (7.1): podtytul mowi, CO dokladnie sie wydarzylo, a nie
 * ze "operacja sie powiodla". Toast bledu ma Ordiego w pozie `think`
 * i akcent koralowy.
 */
import * as React from "react";
import { Mascot } from "../components/Mascot";

type ToastTone = "success" | "error";

interface ToastItem {
  id: number;
  tone: ToastTone;
  title: string;
  subtitle?: string;
  leaving: boolean;
}

interface ToastContextValue {
  success: (title: string, subtitle?: string) => void;
  error: (title: string, subtitle?: string) => void;
}

const ToastContext = React.createContext<ToastContextValue | null>(null);

/** Czasy 1:1 z tabela w sekcji 2.6. */
const TOAST_LIFETIME_MS = 2600;
const TOAST_EXIT_MS = 320;

function ToastCard({ toast, onDismiss }: { toast: ToastItem; onDismiss: () => void }) {
  const isError = toast.tone === "error";
  return (
    <div
      onClick={onDismiss}
      role="status"
      className={`flex max-w-[330px] cursor-pointer items-center gap-[11px] rounded-md border bg-panel-2 py-[11px] pl-[11px] pr-[15px] shadow-toast ${
        toast.leaving ? "animate-toast-out" : "animate-toast-in"
      } ${isError ? "border-coral/50" : "border-line-strong"}`}
    >
      <Mascot pose={isError ? "think" : "happy"} size={30} floaty={false} />
      <div className="flex min-w-0 flex-col gap-0.5">
        <span
          className={`text-[12.5px] font-semibold ${isError ? "text-coral" : "text-white"}`}
        >
          {toast.title}
        </span>
        {toast.subtitle && (
          <span className="text-[11px] leading-snug text-slate-dim">{toast.subtitle}</span>
        )}
      </div>
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastItem[]>([]);
  const nextId = React.useRef(0);

  const dismiss = React.useCallback((id: number) => {
    // Najpierw klasa wyjscia, dopiero po jej zakonczeniu usuniecie z listy -
    // inaczej karta znikalaby skokowo, bez animacji w prawo.
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, leaving: true } : t)));
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, TOAST_EXIT_MS);
  }, []);

  const push = React.useCallback(
    (tone: ToastTone, title: string, subtitle?: string) => {
      const id = nextId.current++;
      setToasts((prev) => [...prev, { id, tone, title, subtitle, leaving: false }]);
      window.setTimeout(() => dismiss(id), TOAST_LIFETIME_MS);
    },
    [dismiss]
  );

  const value = React.useMemo<ToastContextValue>(
    () => ({
      success: (title, subtitle) => push("success", title, subtitle),
      error: (title, subtitle) => push("error", title, subtitle),
    }),
    [push]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-[26px] right-[26px] z-[120] flex flex-col items-end gap-2.5">
        {toasts.map((toast) => (
          <div key={toast.id} className="pointer-events-auto">
            <ToastCard toast={toast} onDismiss={() => dismiss(toast.id)} />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = React.useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast musi być użyty wewnątrz ToastProvider");
  }
  return ctx;
}
