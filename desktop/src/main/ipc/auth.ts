import { ipcMain } from "electron";
import { apiRequest } from "../lib/apiClient";
import { clearSession, getSession, saveSession } from "../lib/tokenStore";
import { toResult } from "../lib/result";

interface LoginResponse {
  token: string;
}

/** Usuwa biale znaki i koncowy slash; dopisuje https:// gdy brak schematu. */
function normalizeBaseUrl(raw: string): string {
  const trimmed = raw.trim().replace(/\/+$/, "");
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  return `https://${trimmed}`;
}

export function registerAuthIpc(): void {
  ipcMain.handle("ordly:auth:getSession", async () => {
    const session = getSession();
    if (!session) {
      return null;
    }
    return { baseUrl: session.baseUrl, username: session.username };
  });

  ipcMain.handle(
    "ordly:auth:login",
    async (_event, rawBaseUrl: string, username: string, password: string) =>
      toResult(async () => {
        const baseUrl = normalizeBaseUrl(rawBaseUrl);
        const { token } = await apiRequest<LoginResponse>(baseUrl, null, "/api/v1/auth/login", {
          method: "POST",
          body: { username, password },
        });
        saveSession({ baseUrl, username, token });
        return { baseUrl, username };
      })
  );

  ipcMain.handle("ordly:auth:logout", async () => {
    clearSession();
  });
}
