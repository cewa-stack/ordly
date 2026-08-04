import type { Config } from "tailwindcss";

/**
 * Tokeny 1:1 z sekcja 2 specyfikacji ORDLY (ordly-koncepcja-wizualna.html).
 * Desktop jest dark-mode-first i nie ma wariantu jasnego - motyw jasny
 * zyje wylacznie w aplikacji mobilnej, jako osobna, swiadoma paleta.
 *
 * Wartosci sa doslowne. Jesli cos ma byc innego odcienia, najpierw
 * zmienia sie specyfikacja, potem ten plik - nie odwrotnie.
 */
export default {
  content: ["./src/renderer/index.html", "./src/renderer/src/**/*.{ts,tsx}"],
  darkMode: undefined,
  theme: {
    extend: {
      colors: {
        ink: "var(--ink)",
        "ink-raised": "var(--ink-raised)",
        panel: "var(--panel)",
        "panel-2": "var(--panel-2)",
        "panel-3": "var(--panel-3)",
        line: "var(--line)",
        "line-strong": "var(--line-strong)",
        teal: "var(--teal)",
        "teal-bright": "var(--teal-bright)",
        "teal-deep": "var(--teal-deep)",
        "teal-dim": "var(--teal-dim)",
        coral: "var(--coral)",
        "coral-dim": "var(--coral-dim)",
        amber: "var(--amber)",
        violet: "var(--violet)",
        slate: "var(--slate)",
        "slate-dim": "var(--slate-dim)",
        white: "var(--white)",
      },
      borderRadius: {
        sm: "8px",
        md: "12px",
        lg: "18px",
        xl: "26px",
      },
      fontFamily: {
        display: ['"Space Grotesk"', '"Segoe UI"', "sans-serif"],
        sans: ["Inter", '"Segoe UI"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', '"SF Mono"', "ui-monospace", "monospace"],
      },
      transitionTimingFunction: {
        ordly: "cubic-bezier(.22,.61,.36,1)",
      },
      boxShadow: {
        window:
          "0 50px 120px -45px rgba(0,0,0,.85), 0 0 0 1px rgba(0,0,0,.35)",
        palette: "0 40px 90px -30px rgba(0,0,0,.9)",
        toast: "0 20px 45px -18px rgba(0,0,0,.85)",
        brand: "0 4px 14px -4px rgba(95,217,204,.5)",
      },
      keyframes: {
        spin360: { to: { transform: "rotate(360deg)" } },
        bob: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-2.5px)" },
        },
        pop: {
          "0%": { transform: "scale(1)" },
          "38%": { transform: "scale(1.2)" },
          "100%": { transform: "scale(1)" },
        },
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
        pulseRing: {
          "0%, 100%": { boxShadow: "0 0 0 4px var(--teal-dim)" },
          "50%": { boxShadow: "0 0 0 8px rgba(95,217,204,.05)" },
        },
      },
      animation: {
        // Czasy 1:1 z tabeli w sekcji 2.6 specyfikacji.
        "spin-ring": "spin360 .95s linear infinite",
        bob: "bob 3.4s ease-in-out infinite",
        "bob-slow": "bob 4s ease-in-out infinite",
        pop: "pop .55s cubic-bezier(.22,.61,.36,1)",
        "fade-up": "fadeUp .28s cubic-bezier(.22,.61,.36,1)",
        "cmd-in": "cmdIn .26s cubic-bezier(.22,.61,.36,1)",
        "toast-in": "toastIn .34s cubic-bezier(.22,.61,.36,1)",
        "toast-out": "toastOut .32s cubic-bezier(.22,.61,.36,1) forwards",
        shimmer: "shimmer 1.3s linear infinite",
        "pulse-ring": "pulseRing 2.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
