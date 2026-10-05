import { ipcMain } from "electron";
import { apiRequest } from "../lib/apiClient";
import { getSession, requireSession } from "../lib/tokenStore";
import { toResult } from "../lib/result";
import {
  type Wholesaler,
  type WholesalerOrderRecord,
  type WholesalerTemplate,
  appendOrderHistory,
  deleteWholesaler,
  deleteWholesalerTemplate,
  listOrderHistory,
  listWholesalerTemplates,
  listWholesalers,
  saveWholesaler,
  saveWholesalerTemplate,
  setDefaultWholesalerTemplate,
} from "../lib/wholesalerStore";

interface HubWholesaleOrder {
  request_id: string;
  wholesaler_id: string;
  wholesaler_name: string;
  sent_at: string;
  subject: string;
  items_summary: string;
  test_mode: boolean;
}

/**
 * Kopia hurtowni i szablonow na Pi - z niej korzysta ekran "Zamow w hurtowni"
 * na ORDLy Control Hub (Hub rozmawia tylko z Pi). Wysylana po kazdej zmianie
 * i przy starcie. Blad (brak sesji, Pi niedostepne) nie psuje zapisu na
 * komputerze - kolejna zmiana albo start aplikacji wysle kopie jeszcze raz.
 */
export async function pushWholesaleCatalogToPi(): Promise<void> {
  const session = getSession();
  if (!session) return;
  try {
    await apiRequest(session.baseUrl, session.token, "/api/v1/hub/wholesale/catalog", {
      method: "PUT",
      body: { wholesalers: listWholesalers(), templates: listWholesalerTemplates() },
    });
  } catch (error) {
    console.warn("Kopia hurtowni na Pi nie wyszla:", error);
  }
}

function afterChange<T>(result: T): T {
  void pushWholesaleCatalogToPi();
  return result;
}

/** Zamowienia wyslane z Huba - do wspolnej historii. Bez Pi: pusta lista. */
async function hubOrderHistory(): Promise<WholesalerOrderRecord[]> {
  const session = getSession();
  if (!session) return [];
  try {
    const orders = await apiRequest<HubWholesaleOrder[]>(
      session.baseUrl,
      session.token,
      "/api/v1/hub/wholesale/orders?limit=50"
    );
    return orders.map((order) => ({
      id: `hub:${order.request_id}`,
      wholesalerId: order.wholesaler_id,
      wholesalerName: order.wholesaler_name,
      sentAt: order.sent_at,
      subject: order.subject,
      itemsSummary: order.items_summary,
      source: "hub",
      testMode: order.test_mode,
    }));
  } catch {
    return [];
  }
}

interface SendOrderPayload {
  wholesalerId: string;
  wholesalerName: string;
  to: string;
  subject: string;
  body: string;
  itemsSummary: string;
}

export function registerWholesalersIpc(): void {
  ipcMain.handle("ordly:wholesalers:list", () => listWholesalers());

  ipcMain.handle(
    "ordly:wholesalers:save",
    (_event, input: Omit<Wholesaler, "id"> & { id?: string }) =>
      afterChange(saveWholesaler(input))
  );

  ipcMain.handle("ordly:wholesalers:delete", (_event, id: string) => {
    afterChange(deleteWholesaler(id));
  });

  ipcMain.handle("ordly:wholesalers:history", async () =>
    [...listOrderHistory(), ...(await hubOrderHistory())].sort(
      (a, b) => new Date(b.sentAt).getTime() - new Date(a.sentAt).getTime()
    )
  );

  ipcMain.handle("ordly:wholesalers:templates", () => listWholesalerTemplates());

  ipcMain.handle(
    "ordly:wholesalers:saveTemplate",
    (_event, input: Omit<WholesalerTemplate, "id" | "isDefault"> & { id?: string }) =>
      afterChange(saveWholesalerTemplate(input))
  );

  ipcMain.handle("ordly:wholesalers:setDefaultTemplate", (_event, id: string) => {
    afterChange(setDefaultWholesalerTemplate(id));
  });

  ipcMain.handle("ordly:wholesalers:deleteTemplate", (_event, id: string) => {
    afterChange(deleteWholesalerTemplate(id));
  });

  ipcMain.handle("ordly:wholesalers:sendOrder", async (_event, payload: SendOrderPayload) =>
    toResult(async () => {
      const session = requireSession();
      await apiRequest(session.baseUrl, session.token, "/api/v1/mail/send-wholesaler-order", {
        method: "POST",
        body: { to: payload.to, subject: payload.subject, body: payload.body },
      });
      appendOrderHistory({
        wholesalerId: payload.wholesalerId,
        wholesalerName: payload.wholesalerName,
        sentAt: new Date().toISOString(),
        subject: payload.subject,
        itemsSummary: payload.itemsSummary,
      });
      return null;
    })
  );
}
