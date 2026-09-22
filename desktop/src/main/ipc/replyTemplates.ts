import { ipcMain } from "electron";
import { apiRequest } from "../lib/apiClient";
import { requireSession } from "../lib/tokenStore";
import { toResult } from "../lib/result";

/**
 * Szablony odpowiedzi w dyskusjach. Zyja na Pi, zeby telefon i desktop
 * mialy te same - zmienia je wylacznie desktop (Ustawienia).
 */
export function registerReplyTemplatesIpc(): void {
  ipcMain.handle("ordly:templates:list", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/reply-templates");
    })
  );

  ipcMain.handle("ordly:templates:create", async (_event, input: { title: string; body: string }) =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/reply-templates", {
        method: "POST",
        body: { title: input.title, body: input.body },
      });
    })
  );

  ipcMain.handle(
    "ordly:templates:update",
    async (_event, id: number, input: { title: string; body: string }) =>
      toResult(async () => {
        const session = requireSession();
        return apiRequest(session.baseUrl, session.token, `/api/v1/reply-templates/${id}`, {
          method: "PUT",
          body: { title: input.title, body: input.body },
        });
      })
  );

  ipcMain.handle("ordly:templates:delete", async (_event, id: number) =>
    toResult(async () => {
      const session = requireSession();
      await apiRequest(session.baseUrl, session.token, `/api/v1/reply-templates/${id}`, {
        method: "DELETE",
      });
      return null;
    })
  );
}
