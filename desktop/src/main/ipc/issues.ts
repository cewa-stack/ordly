import { ipcMain } from "electron";
import { apiRequest } from "../lib/apiClient";
import { requireSession } from "../lib/tokenStore";
import { toResult } from "../lib/result";

export function registerIssuesIpc(): void {
  ipcMain.handle("ordly:issues:list", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/issues");
    })
  );

  ipcMain.handle("ordly:issues:messages", async (_event, issueId: string) =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(
        session.baseUrl,
        session.token,
        `/api/v1/issues/${encodeURIComponent(issueId)}/messages`
      );
    })
  );

  ipcMain.handle("ordly:issues:reply", async (_event, issueId: string, text: string) =>
    toResult(async () => {
      const session = requireSession();
      await apiRequest(
        session.baseUrl,
        session.token,
        `/api/v1/issues/${encodeURIComponent(issueId)}/reply`,
        { method: "POST", body: { text } }
      );
      return null;
    })
  );
}
