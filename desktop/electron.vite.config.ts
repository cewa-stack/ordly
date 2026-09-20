import { resolve } from "path";
import { readFileSync } from "fs";
import { defineConfig, externalizeDepsPlugin } from "electron-vite";
import react from "@vitejs/plugin-react";

/**
 * Wersja aplikacji bierze sie z package.json, a nie z napisu wpisanego
 * w pasku bocznym. Wczesniej stalo tam na sztywno "v2" i po kazdym
 * wydaniu klamalo.
 */
const version = JSON.parse(
  readFileSync(resolve(__dirname, "package.json"), "utf-8")
).version as string;

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
  },
  renderer: {
    define: {
      __APP_VERSION__: JSON.stringify(version),
    },
    resolve: {
      alias: {
        "@renderer": resolve("src/renderer/src"),
      },
    },
    plugins: [react()],
  },
});
