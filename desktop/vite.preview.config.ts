/**
 * Konfiguracja PODGLADU UKLADU - `npm run preview:ui`.
 *
 * Osobna od electron-vite: podglad chodzi w zwyklej przegladarce, bez
 * procesu glownego Electrona i bez Pi. Sluzy do sprawdzenia siatek,
 * odstepow i przepelnien (lista kontrolna z sekcji 15 instrukcji).
 */
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  root: resolve(__dirname, "preview"),
  plugins: [react()],
  server: { port: 8932, strictPort: true },
});
