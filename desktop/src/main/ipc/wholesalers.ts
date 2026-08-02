import { ipcMain } from "electron";
import { apiRequest } from "../lib/apiClient";
import { requireSession } from "../lib/tokenStore";
import { toResult } from "../lib/result";
import {
  type Wholesaler,
  appendOrderHistory,
  deleteWholesaler,
  listOrderHistory,
  listWholesalers,
  saveWholesaler,
} from "../lib/wholesalerStore";

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
    (_event, input: Omit<Wholesaler, "id"> & { id?: string }) => saveWholesaler(input)
  );

  ipcMain.handle("ordly:wholesalers:delete", (_event, id: string) => {
    deleteWholesaler(id);
  });

  ipcMain.handle("ordly:wholesalers:history", () => listOrderHistory());

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
