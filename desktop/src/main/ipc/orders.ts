import { ipcMain } from "electron";
import { apiRequest } from "../lib/apiClient";
import { requireSession } from "../lib/tokenStore";
import { toResult } from "../lib/result";

export function registerOrdersIpc(): void {
  ipcMain.handle("ordly:orders:list", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/orders");
    })
  );

  ipcMain.handle("ordly:orders:sync", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/orders/sync", {
        method: "POST",
      });
    })
  );
}
