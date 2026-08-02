/**
 * System toastów - zastępuje rozrzucone, niespójne komunikaty inline
 * ("Zsynchronizowano...", błędy mutacji) jednym, spójnym, "premium"
 * wzorcem: karta w rogu ekranu, ikona statusu w kółku, auto-znikanie.
 * Wywoływane przez `useToast()` z dowolnego ekranu (musi być pod
 * `ToastProvider`, zamontowanym raz w App.tsx).
 */
import * as React from "react";

type ToastType = "success" | "error";

interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  success: (message: string) => void;
  error: (message: string) => void;
}

const ToastContext = React.createContext<ToastContextValue | null>(null);

const AUTO_DISMISS_MS = 4500;

function CheckCircleGlyph() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M4 12.5l5 5L20 6.5" stroke="currentColor" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function AlertGlyph() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M12 8v5" stroke="currentColor" strokeWidth={3} strokeLinecap="round" />
      <circle cx="12" cy="16.3" r="1" fill="currentColor" />
    </svg>
  );
}

function ToastCard({ toast, onDismiss }: { toast: ToastItem; onDismiss: () => void }) {
  const isSuccess = toast.type === "success";
  return (
    <div
      onClick={onDismiss}
      className="animate-toast-in flex w-[340px] cursor-pointer items-center gap-3 rounded-2xl border border-border bg-surface px-4 py-3.5 shadow-[0_16px_40px_-12px_rgba(0,0,0,0.6)]"
      role="status"
    >
      <span
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
          isSuccess ? "bg-success text-on-primary" : "bg-danger text-on-primary"
        }`}
      >
        {isSuccess ? <CheckCircleGlyph /> : <AlertGlyph />}
      </span>
      <p className="text-callout leading-snug text-text">{toast.message}</p>
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastItem[]>([]);
  const nextId = React.useRef(0);

  const dismiss = React.useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = React.useCallback(
    (type: ToastType, message: string) => {
      const id = nextId.current++;
      setToasts((prev) => [...prev, { id, type, message }]);
      window.setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
    },
    [dismiss]
  );

  const value = React.useMemo<ToastContextValue>(
    () => ({
      success: (message: string) => push("success", message),
      error: (message: string) => push("error", message),
    }),
    [push]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-6 right-6 z-50 flex flex-col-reverse gap-2.5">
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
