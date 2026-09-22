/**
 * Konfiguracja PODGLADU UKLADU - `npm run preview:ui`.
 *
 * Osobna od electron-vite: podglad chodzi w zwyklej przegladarce, bez
 * procesu glownego Electrona i bez Pi. Sluzy do sprawdzenia siatek,
 * odstepow i przepelnien (lista kontrolna z sekcji 15 instrukcji).
 */
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "fs";
import { resolve } from "path";

// Ta sama stala co w electron.vite.config.ts - bez niej ShellLayout
// wywracal sie na `__APP_VERSION__ is not defined` i podglad byl pusty.
const version = JSON.parse(readFileSync(resolve(__dirname, "package.json"), "utf-8"))
  .version as string;

export default defineConfig({
  root: resolve(__dirname, "preview"),
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(version),
  },
  server: { port: 8932, strictPort: true },
});
