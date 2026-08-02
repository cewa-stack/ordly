import type { Config } from "tailwindcss";

/**
 * Tokeny 1:1 z mobile/src/theme/colors.ts - ORDLY ma jedna, ciemna
 * paleta marki (bez trybu jasnego), wiec zadnej wersji "light" tutaj
 * celowo nie ma.
 */
export default {
  content: ["./src/renderer/index.html", "./src/renderer/src/**/*.{ts,tsx}"],
  darkMode: undefined,
  theme: {
    extend: {
      colors: {
        primary: "var(--ordly-primary)",
        secondary: "var(--ordly-secondary)",
        accent: "var(--ordly-accent)",
        background: "var(--ordly-background)",
        surface: "var(--ordly-surface)",
        "surface-raised": "var(--ordly-surface-raised)",
        border: "var(--ordly-border)",
        success: "var(--ordly-success)",
        warning: "var(--ordly-warning)",
        danger: "var(--ordly-danger)",
        text: "var(--ordly-text)",
        "text-secondary": "var(--ordly-text-secondary)",
        "text-dim": "var(--ordly-text-dim)",
        "on-primary": "var(--ordly-on-primary)",
        "primary-tint": "var(--ordly-primary-tint)",
        "success-tint": "var(--ordly-success-tint)",
        "warning-tint": "var(--ordly-warning-tint)",
        "danger-tint": "var(--ordly-danger-tint)",
      },
      borderRadius: {
        xs: "10px",
        sm: "12px",
        md: "14px",
        lg: "16px",
        xl: "20px",
        sheet: "24px",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
        mono: ["ui-monospace", '"SF Mono"', "Menlo", "Consolas", "monospace"],
      },
      keyframes: {
        floaty: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
        pulseDot: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.45" },
        },
      },
      animation: {
        floaty: "floaty 3.8s ease-in-out infinite",
        "pulse-dot": "pulseDot 2.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
