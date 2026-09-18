import { ipcMain } from "electron";
import { apiRequest } from "../lib/apiClient";
import { requireSession } from "../lib/tokenStore";
import { toResult } from "../lib/result";

export interface OfferRef {
  marketplace: string;
  externalId: string;
}

export interface OfferQuantityPayload {
  quantity: number;
  reason: string;
}

/**
 * Ścieżka jednej oferty.
 *
 * Identyfikator idzie przez `encodeURIComponent`, bo bywa ze slashem
 * (Allegro Lokalnie). Backend trzyma dla tych tras wzorzec `{...:path}`,
 * więc rozkodowany slash go nie rozsypie.
 */
function offerPath(offer: OfferRef): string {
  return `/api/v1/stock/offers/${encodeURIComponent(offer.marketplace)}/${encodeURIComponent(
    offer.externalId
  )}`;
}

export function registerStockIpc(): void {
  ipcMain.handle("ordly:stock:offers", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/stock/offers");
    })
  );

  ipcMain.handle("ordly:stock:sync", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/stock/sync", {
        method: "POST",
      });
    })
  );

  ipcMain.handle(
    "ordly:stock:setQuantity",
    async (_event, offer: OfferRef, payload: OfferQuantityPayload) =>
      toResult(async () => {
        const session = requireSession();
        return apiRequest(session.baseUrl, session.token, `${offerPath(offer)}/quantity`, {
          method: "PUT",
          body: payload,
        });
      })
  );

  ipcMain.handle("ordly:stock:history", async (_event, offer: OfferRef) =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, `${offerPath(offer)}/history?limit=20`);
    })
  );
}
