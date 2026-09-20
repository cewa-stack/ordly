/**
 * Ordlak - maskotka ORDLY jako jeden komponent SVG (sekcja 6 instrukcji
 * "Nokturn"). Zastepuje osiem plikow PNG i cala warstwe wybierania pozy
 * po nazwie pliku.
 *
 * ZADNYCH `id` W SVG. Komponent montuje sie wielokrotnie na jednym
 * ekranie (pasek boczny, karta powitalna, notka w panelu szczegolu),
 * a duplikaty `id` psuja gradienty i maski w calym dokumencie.
 *
 * Caly wyglad i ruch siedzi w theme/global.css pod `[data-state="..."]`.
 * Tutaj jest wylacznie geometria - dzieki temu ten sam kształt obsluguje
 * szesc stanow bez jednej galezi w kodzie.
 *
 * Rozmiar nadaje OPAKOWANIE, nie SVG: `<span>` dostaje width/height,
 * a SVG ma `width:100%; height:100%` (global.css). Ponizej 22 px Ordlak
 * traci oczy - to dolna granica.
 */

export type OrdlakState = "idle" | "sync" | "think" | "happy" | "alert" | "sleep";

interface OrdlakProps {
  state?: OrdlakState;
  size?: number;
  className?: string;
}

export function Ordlak({ state = "idle", size = 40, className = "" }: OrdlakProps) {
  return (
    <span
      className={`ordlak ${className}`}
      data-state={state}
      style={{ width: size, height: size, lineHeight: 0 }}
    >
      {/*
       * Stan NIE jest w etykiecie (sekcja 14): czytnik ekranu nie ma
       * powtarzac "Ordlak synchronizuje" przy kazdym odswiezeniu.
       * Stan komunikuje tekst obok maskotki.
       */}
      <svg viewBox="0 0 128 128" role="img" aria-label="Ordlak">
        <g className="ord-shift">
          <ellipse className="ord-shadow" cx="60" cy="118" rx="29" ry="4.6" />
          <g className="ord-figure">
            <rect className="ord-foot" x="36" y="101" width="16" height="12" rx="6" />
            <rect className="ord-foot" x="64" y="101" width="16" height="12" rx="6" />
            <g className="ord-ant">
              <line className="ord-ant-stem" x1="60" y1="46" x2="60" y2="27" />
              <circle className="ord-ant-bulb" cx="60" cy="22" r="6" />
            </g>
            <rect className="ord-body" x="26" y="44" width="68" height="64" rx="28" />
            <g className="ord-eyes">
              <ellipse className="ord-eye" cx="48" cy="70" rx="6" ry="7" />
              <ellipse className="ord-eye" cx="72" cy="70" rx="6" ry="7" />
              <circle className="ord-glint" cx="50.2" cy="66.8" r="2" />
              <circle className="ord-glint" cx="74.2" cy="66.8" r="2" />
              <path className="ord-arc" d="M42 72q6-8 12 0" />
              <path className="ord-arc" d="M66 72q6-8 12 0" />
              <path className="ord-lid" d="M42 69q6 6 12 0" />
              <path className="ord-lid" d="M66 69q6 6 12 0" />
            </g>
            <path className="ord-mouth" d="M52 86q8 6 16 0" />
            <path className="ord-mouth-worry" d="M52 88q8-6 16 0" />
            <g transform="rotate(7 101 81)">
              <rect className="ord-board" x="86" y="62" width="30" height="38" rx="5" />
              <rect className="ord-clip" x="95" y="57" width="12" height="8" rx="3" />
              <line className="ord-boardline" x1="92" y1="76" x2="110" y2="76" />
              <line className="ord-boardline" x1="92" y1="84" x2="110" y2="84" />
              <line className="ord-boardline" x1="92" y1="92" x2="104" y2="92" />
            </g>
          </g>
          {/*
           * Fale MUSZA byc poza `.ord-figure`, jako rodzenstwo wewnatrz
           * `.ord-shift`. Wewnatrz psuja ramke figury (a przez to
           * wysrodkowanie) i punkt obrotu animacji bob/hop.
           *
           * Sygnal wychodzi z anteny, nie z pierscienia wokol postaci:
           * sylwetka nie jest okragla, wiec kolo ocieralo sie o notatnik
           * po prawej i zostawialo pustke po lewej.
           */}
          <g className="ord-wave">
            <path d="M51.8 16.3A10 10 0 0 1 68.2 16.3" />
            <path d="M47.7 13.4A15 15 0 0 1 72.3 13.4" />
            <path d="M43.6 10.5A20 20 0 0 1 76.4 10.5" />
          </g>
          <g className="ord-think">
            <circle cx="98" cy="36" r="3" />
            <circle cx="108" cy="27" r="3.8" />
            <circle cx="119" cy="17" r="4.6" />
          </g>
          <g className="ord-bang">
            <path d="M100 20v14" />
            <path d="M100 42v.5" />
          </g>
          <g className="ord-zzz">
            <text x="96" y="36" fontSize="15">
              z
            </text>
            <text x="108" y="22" fontSize="20">
              z
            </text>
          </g>
          <g className="ord-spark">
            <path d="M100 25 102.5 31.5 109 34 102.5 36.5 100 43 97.5 36.5 91 34 97.5 31.5Z" />
            <path d="M26 35.5 27.8 40.2 32.5 42 27.8 43.8 26 48.5 24.2 43.8 19.5 42 24.2 40.2Z" />
          </g>
        </g>
      </svg>
    </span>
  );
}
