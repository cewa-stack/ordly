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

  ipcMain.handle("ordly:orders:search", async (_event, query: string) =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(
        session.baseUrl,
        session.token,
        `/api/v1/orders/search?q=${encodeURIComponent(query)}`
      );
    })
  );

  ipcMain.handle("ordly:orders:tracking", async (_event, externalId: string) =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(
        session.baseUrl,
        session.token,
        `/api/v1/orders/${encodeURIComponent(externalId)}/tracking`
      );
    })
  );

  ipcMain.handle(
    "ordly:orders:setFulfillment",
    async (_event, externalId: string, status: string) =>
      toResult(async () => {
        const session = requireSession();
        return apiRequest(
          session.baseUrl,
          session.token,
          `/api/v1/orders/${encodeURIComponent(externalId)}/fulfillment`,
          { method: "POST", body: { status } }
        );
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
