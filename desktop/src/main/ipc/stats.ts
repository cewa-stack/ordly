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

  ipcMain.handle("ordly:stats:stockReport", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/stock/report");
    })
  );

  ipcMain.handle("ordly:stats:shoppingList", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/stock/shopping-list");
    })
  );
}
