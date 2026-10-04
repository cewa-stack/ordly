import { ipcMain } from "electron";
import { apiRequest } from "../lib/apiClient";
import { requireSession } from "../lib/tokenStore";
import { toResult } from "../lib/result";

export function registerReturnsIpc(): void {
  ipcMain.handle("ordly:returns:list", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/returns");
    })
  );

  // Rejestr anulowan i zwrotow pieniedzy (/api/v1/customer-cases).
  ipcMain.handle("ordly:cases:list", async (_event, query: Record<string, unknown> = {}) =>
    toResult(async () => {
      const session = requireSession();
      const params = new URLSearchParams();
      for (const [key, value] of Object.entries(query)) {
        if (value === undefined || value === null || value === "") continue;
        if (Array.isArray(value)) value.forEach((item) => params.append(key, String(item)));
        else params.append(key, String(value));
      }
      const suffix = params.toString() ? `?${params.toString()}` : "";
      return apiRequest(session.baseUrl, session.token, `/api/v1/customer-cases${suffix}`);
    })
  );

  ipcMain.handle("ordly:cases:update", async (_event, id: number, update: unknown) =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, `/api/v1/customer-cases/${Number(id)}`, {
        method: "PATCH",
        body: update,
      });
    })
  );

  ipcMain.handle("ordly:cases:reasonHistory", async (_event, id: number) =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(
        session.baseUrl,
        session.token,
        `/api/v1/customer-cases/${Number(id)}/reason-history`
      );
    })
  );
}
