import type { Config } from "tailwindcss";

/**
 * Tokeny 1:1 z sekcja 4 instrukcji "ORDLY Nokturn". Kazdy kolor jest
 * odnosnikiem do zmiennej CSS z theme/global.css - tutaj NIE MA
 * wartosci szesnastkowych poza cieniami, ktorych Tailwind nie umie
 * zlozyc ze zmiennej z przezroczystoscia.
 *
 * Desktop jest wylacznie nocny (decyzja 1 z sekcji 16) - motyw dzienny
 * zyje tylko w aplikacji mobilnej, jako osobna, swiadoma paleta.
 *
 * Wartosci sa doslowne. Jesli cos ma byc innego odcienia, najpierw
 * zmienia sie instrukcja, potem global.css - nie odwrotnie.
 */
export default {
  content: ["./src/renderer/index.html", "./src/renderer/src/**/*.{ts,tsx}"],
  darkMode: undefined,
  theme: {
    extend: {
      colors: {
        void: "var(--void)",
        base: "var(--base)",
        panel: "var(--panel)",
        "panel-2": "var(--panel-2)",
        "panel-3": "var(--panel-3)",
        line: "var(--line)",
        "line-2": "var(--line-2)",
        text: "var(--text)",
        "text-2": "var(--text-2)",
        "text-3": "var(--text-3)",
        teal: "var(--teal)",
        "teal-2": "var(--teal-2)",
        "teal-deep": "var(--teal-deep)",
        "teal-glow": "var(--teal-glow)",
        coral: "var(--coral)",
        "coral-glow": "var(--coral-glow)",
        amber: "var(--amber)",
        violet: "var(--violet)",
        /** Ton "zamkniete" - pigulki i wygaszone etykiety. */
        mute: "var(--mute-tint)",
        /** Tla etykiet kanalow sprzedazy (sekcja 7). */
        "chan-allegro": "var(--chan-allegro)",
        "chan-lokalnie": "var(--chan-lokalnie)",
        "chan-lokalnie-tx": "var(--chan-lokalnie-tx)",
        "chan-olx": "var(--chan-olx)",
        "chan-amazon": "var(--chan-amazon)",
        "chan-lokalnie-bar": "var(--chan-lokalnie-bar)",
        /* Odcienie pochodne - patrz global.css. */
        "amber-soft": "var(--amber-soft)",
        "coral-soft": "var(--coral-soft)",
        "coral-line": "var(--coral-line)",
        "coral-deep": "var(--coral-deep)",
        "teal-2-glow": "var(--teal-2-glow)",
        /** Tekst na wypelnieniu - CTA, gałka strzalki, przycisk kasowania. */
        "on-teal": "var(--on-teal)",
        "on-coral": "var(--on-coral)",
        /** Przyciemnienie pod modalem i paleta polecen. */
        scrim: "var(--scrim)",
      },
      borderRadius: {
        xs: "var(--r-xs)",
        sm: "var(--r-sm)",
        md: "var(--r-md)",
        lg: "var(--r-lg)",
        xl: "var(--r-xl)",
        pill: "var(--r-pill)",
      },
      fontFamily: {
        display: [
          '"Bricolage Grotesque Variable"',
          '"Bricolage Grotesque"',
          '"Space Grotesk"',
          "system-ui",
          "sans-serif",
        ],
        sans: ['"Instrument Sans"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      transitionTimingFunction: {
        ordly: "cubic-bezier(.22,.61,.36,1)",
      },
      boxShadow: {
        /** Swiecacy punkt - wylacznie przycisk `primary` (sekcja 7). */
        "glow-teal": "0 6px 22px -8px rgba(95,217,204,.7)",
        window: "0 50px 120px -45px rgba(0,0,0,.85), 0 0 0 1px rgba(0,0,0,.35)",
        palette: "0 40px 90px -30px rgba(0,0,0,.9)",
        toast: "0 20px 45px -18px rgba(0,0,0,.85)",
      },
      keyframes: {
        spin360: { to: { transform: "rotate(360deg)" } },
        fadeUp: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "none" },
        },
        cmdIn: {
          from: { opacity: "0", transform: "translateY(-12px) scale(.98)" },
          to: { opacity: "1", transform: "none" },
        },
        toastIn: {
          from: { opacity: "0", transform: "translateX(22px)" },
          to: { opacity: "1", transform: "none" },
        },
        toastOut: { to: { opacity: "0", transform: "translateX(22px)" } },
        shimmer: { to: { backgroundPosition: "-200% 0" } },
      },
      animation: {
        // Czasy 1:1 z tabela w sekcji 14: 150 ms kontrolka,
        // 280 ms wejscie panelu i przejscie ekranu.
        "spin-ring": "spin360 .95s linear infinite",
        "fade-up": "fadeUp .28s cubic-bezier(.22,.61,.36,1)",
        "cmd-in": "cmdIn .26s cubic-bezier(.22,.61,.36,1)",
        "toast-in": "toastIn .34s cubic-bezier(.22,.61,.36,1)",
        "toast-out": "toastOut .32s cubic-bezier(.22,.61,.36,1) forwards",
        shimmer: "shimmer 1.3s linear infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
