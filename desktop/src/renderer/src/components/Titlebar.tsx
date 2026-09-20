/**
 * Chrome okna - 38 px (sekcja 8 instrukcji). Okno jest bezramkowe
 * (main/index.ts: frame:false), wiec min/maks/zamknij rysujemy sami.
 *
 * Kropka "live" swieci tylko wtedy, gdy Pi faktycznie odpowiada -
 * inaczej byloby to swiatelko, ktore zawsze swieci na zielono.
 */
interface TitlebarProps {
  online: boolean;
  hostname: string;
}

export function Titlebar({ online, hostname }: TitlebarProps) {
  return (
    <div className="app-region-drag flex h-[38px] shrink-0 items-center gap-2 border-b border-line px-4">
      <div className="o-mono mx-auto flex items-center gap-2 text-[10.5px] uppercase tracking-[.1em] text-text-3">
        <span
          className={`h-[5px] w-[5px] rounded-full ${online ? "bg-teal" : "bg-coral"}`}
          style={online ? { boxShadow: "0 0 0 4px var(--teal-glow)" } : undefined}
        />
        ORDLY · {online ? hostname : "brak połączenia z Pi"}
      </div>

      <div className="app-region-no-drag flex items-center gap-4 text-text-3">
        <button
          aria-label="Minimalizuj"
          onClick={() => void window.ordly.window.minimize()}
          className="transition-colors duration-150 hover:text-text"
        >
          <svg width="11" height="11" viewBox="0 0 11 11">
            <line x1="1" y1="5.5" x2="10" y2="5.5" stroke="currentColor" strokeWidth="1.1" />
          </svg>
        </button>
        <button
          aria-label="Maksymalizuj"
          onClick={() => void window.ordly.window.maximize()}
          className="transition-colors duration-150 hover:text-text"
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
          className="transition-colors duration-150 hover:text-coral"
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
