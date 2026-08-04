/**
 * Chrome okna, 40 px (sekcja 4.1). Okno jest bezramkowe
 * (main/index.ts: frame:false), wiec min/maks/zamknij rysujemy sami.
 *
 * Kropka "live" pulsuje tylko wtedy, gdy Pi faktycznie odpowiada -
 * inaczej byloby to swiatelko, ktore zawsze swieci na zielono.
 */
interface TitlebarProps {
  online: boolean;
  hostname: string;
}

export function Titlebar({ online, hostname }: TitlebarProps) {
  return (
    <div className="app-region-drag flex h-10 shrink-0 items-center gap-2 border-b border-line bg-ink-raised px-4">
      <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
      <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
      <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />

      <div className="o-mono mx-auto flex items-center gap-2 text-[11px] tracking-[.04em] text-slate-dim">
        <span
          className={`h-[5px] w-[5px] rounded-full ${
            online ? "animate-pulse-ring bg-teal-bright" : "bg-coral"
          }`}
        />
        ORDLY <b className="font-medium text-slate">—</b>{" "}
        {online ? hostname : "brak połączenia z Pi"}
      </div>

      <div className="app-region-no-drag flex items-center gap-4 text-slate-dim">
        <button
          aria-label="Minimalizuj"
          onClick={() => void window.ordly.window.minimize()}
          className="hover:text-white"
        >
          <svg width="11" height="11" viewBox="0 0 11 11">
            <line x1="1" y1="5.5" x2="10" y2="5.5" stroke="currentColor" strokeWidth="1.1" />
          </svg>
        </button>
        <button
          aria-label="Maksymalizuj"
          onClick={() => void window.ordly.window.maximize()}
          className="hover:text-white"
        >
          <svg width="11" height="11" viewBox="0 0 11 11">
            <rect
              x="1"
              y="1"
              width="9"
              height="9"
              rx="1.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.1"
            />
          </svg>
        </button>
        <button
          aria-label="Zamknij"
          onClick={() => void window.ordly.window.close()}
          className="hover:text-coral"
        >
          <svg width="11" height="11" viewBox="0 0 11 11">
            <line x1="1" y1="1" x2="10" y2="10" stroke="currentColor" strokeWidth="1.1" />
            <line x1="10" y1="1" x2="1" y2="10" stroke="currentColor" strokeWidth="1.1" />
          </svg>
        </button>
      </div>
    </div>
  );
}
