import { ipcMain } from "electron";
import { apiRequest } from "../lib/apiClient";
import { requireSession } from "../lib/tokenStore";
import { toResult } from "../lib/result";

interface ListFilters {
  source?: "allegro" | "olx" | "other";
  unreadOnly?: boolean;
}

export function registerMailboxIpc(): void {
  ipcMain.handle("ordly:mailbox:list", async (_event, filters: ListFilters = {}) =>
    toResult(async () => {
      const session = requireSession();
      const params = new URLSearchParams();
      if (filters.source) params.set("source", filters.source);
      if (filters.unreadOnly) params.set("unread_only", "true");
      const query = params.toString();
      return apiRequest(
        session.baseUrl,
        session.token,
        `/api/v1/mail/messages${query ? `?${query}` : ""}`
      );
    })
  );

  ipcMain.handle("ordly:mailbox:status", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/mail/status");
    })
  );

  ipcMain.handle("ordly:mailbox:sync", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/mail/sync", {
        method: "POST",
      });
    })
  );

  ipcMain.handle("ordly:mailbox:markRead", async (_event, messageId: string) =>
    toResult(async () => {
      const session = requireSession();
      await apiRequest(
        session.baseUrl,
        session.token,
        `/api/v1/mail/messages/${encodeURIComponent(messageId)}/mark-read`,
        { method: "POST" }
      );
      return null;
    })
  );
}
