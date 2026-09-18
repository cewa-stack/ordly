import { ipcMain } from "electron";
import { apiRequest } from "../lib/apiClient";
import { requireSession } from "../lib/tokenStore";
import { toResult } from "../lib/result";

export function registerStatsIpc(): void {
  ipcMain.handle("ordly:stats:get", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/stats");
    })
  );

  ipcMain.handle("ordly:stats:dashboard", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/dashboard");
    })
  );

  ipcMain.handle("ordly:stats:health", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/health");
    })
  );

  ipcMain.handle("ordly:stats:events", async () =>
    toResult(async () => {
      const session = requireSession();
      // Bez wpisow synchronizacji - powstaja co minute i zaslanialy
      // zamowienia, zwroty i ostrzezenia na liscie "Dziś w systemie".
      return apiRequest(
        session.baseUrl,
        session.token,
        "/api/v1/logs?limit=60&include_sync=false"
      );
    })
  );

  // Uwaga: `/backup/trigger` celowo NIE ma prefiksu `/api/v1` - endpoint
  // istnieje od czasu, zanim API dostalo wersjonowanie, i jest tak
  // wolany przez lokalny monitoring na Pi.
  ipcMain.handle("ordly:stats:backup", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/backup/trigger", {
        method: "POST",
      });
    })
  );
}
