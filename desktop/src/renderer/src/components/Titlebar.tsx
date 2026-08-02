import type { ReactNode } from "react";

interface TitlebarProps {
  status?: ReactNode;
}

/** Pasek tytulowy bezramkowego okna - wlasne min/maks/zamknij (patrz main/index.ts: frame:false). */
export function Titlebar({ status }: TitlebarProps) {
  return (
    <div className="app-region-drag flex h-10 shrink-0 items-center justify-between border-b border-border bg-surface pl-4 pr-3">
      <div className="flex items-center gap-2 font-mono text-[10.5px] uppercase tracking-[0.12em] text-text-dim">
        <span className="h-1.5 w-1.5 rounded-full bg-primary shadow-[0_0_8px_rgba(86,224,208,0.7)]" />
        ORDLY Desktop
      </div>
      {status}
      <div className="app-region-no-drag flex items-center gap-4 text-text-dim">
        <button aria-label="Minimalizuj" onClick={() => void window.ordly.window.minimize()} className="hover:text-text">
          <svg width="11" height="11" viewBox="0 0 11 11">
            <line x1="1" y1="5.5" x2="10" y2="5.5" stroke="currentColor" strokeWidth="1.1" />
          </svg>
        </button>
        <button aria-label="Maksymalizuj" onClick={() => void window.ordly.window.maximize()} className="hover:text-text">
          <svg width="11" height="11" viewBox="0 0 11 11">
            <rect x="1" y="1" width="9" height="9" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.1" />
          </svg>
        </button>
        <button aria-label="Zamknij" onClick={() => void window.ordly.window.close()} className="hover:text-danger">
          <svg width="11" height="11" viewBox="0 0 11 11">
            <line x1="1" y1="1" x2="10" y2="10" stroke="currentColor" strokeWidth="1.1" />
            <line x1="10" y1="1" x2="1" y2="10" stroke="currentColor" strokeWidth="1.1" />
          </svg>
        </button>
      </div>
    </div>
  );
}
