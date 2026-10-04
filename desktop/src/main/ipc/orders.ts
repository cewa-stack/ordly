import { ipcMain } from "electron";
import { apiRequest } from "../lib/apiClient";
import { requireSession } from "../lib/tokenStore";
import { toResult } from "../lib/result";

export function registerOrdersIpc(): void {
  ipcMain.handle("ordly:orders:list", async () =>
    toResult(async () => {
      const session = requireSession();
      // 100 to maksimum API. Domyslne 20 ucinalo liste, liczniki "do
      // spakowania" i statystyki kanalow do 20 ostatnich zamowien.
      return apiRequest(session.baseUrl, session.token, "/api/v1/orders?limit=100");
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

  // Jedno zamowienie - np. numer przesylki do szablonu odpowiedzi, gdy
  // dyskusja dotyczy zamowienia spoza 100 ostatnich z listy.
  ipcMain.handle("ordly:orders:get", async (_event, externalId: string) =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(
        session.baseUrl,
        session.token,
        `/api/v1/orders/${encodeURIComponent(externalId)}`
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

  // Status aplikacyjny - zmiana TYLKO w ORDLY, nic nie idzie do Allegro.
  // `status: null` = "Przywroc status z Allegro".
  ipcMain.handle(
    "ordly:orders:setAppStatus",
    async (_event, externalId: string, status: string | null) =>
      toResult(async () => {
        const session = requireSession();
        return apiRequest(
          session.baseUrl,
          session.token,
          `/api/v1/orders/${encodeURIComponent(externalId)}/app-status`,
          { method: "POST", body: { status } }
        );
      })
  );

  ipcMain.handle("ordly:orders:appStatusHistory", async (_event, externalId: string) =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(
        session.baseUrl,
        session.token,
        `/api/v1/orders/${encodeURIComponent(externalId)}/app-status/history`
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
