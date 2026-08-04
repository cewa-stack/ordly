import { ipcMain } from "electron";
import { apiRequest } from "../lib/apiClient";
import { requireSession } from "../lib/tokenStore";
import { toResult } from "../lib/result";

export interface StockAdjustPayload {
  op: "set" | "add" | "remove" | "min";
  quantity: number;
  reason?: string;
}

export interface StockCreatePayload {
  sku: string;
  name: string;
  min_stock: number;
}

export function registerStockIpc(): void {
  ipcMain.handle("ordly:stock:list", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/stock");
    })
  );

  ipcMain.handle("ordly:stock:create", async (_event, payload: StockCreatePayload) =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/stock", {
        method: "POST",
        body: payload,
      });
    })
  );

  ipcMain.handle("ordly:stock:history", async (_event, sku: string) =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(
        session.baseUrl,
        session.token,
        `/api/v1/stock/${encodeURIComponent(sku)}/history?limit=20`
      );
    })
  );

  ipcMain.handle(
    "ordly:stock:adjust",
    async (_event, sku: string, payload: StockAdjustPayload) =>
      toResult(async () => {
        const session = requireSession();
        return apiRequest(
          session.baseUrl,
          session.token,
          `/api/v1/stock/${encodeURIComponent(sku)}/adjust`,
          { method: "POST", body: payload }
        );
      })
  );
}
