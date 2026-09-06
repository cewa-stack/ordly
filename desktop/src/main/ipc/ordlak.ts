/**
 * IPC Ordlaka - asystent aplikacji.
 *
 * Historia rozmowy zyje w bazie na Pi, wiec renderer wysyla POJEDYNCZE
 * pytanie plus numer watku - nie cala rozmowe. Zapis odpowiedzi do pliku
 * jest jedyna operacja czysto lokalna: okno zapisu i `writeFile` moga
 * dzialac tylko w procesie glownym.
 */
import { BrowserWindow, dialog, ipcMain } from "electron";
import { writeFileSync } from "node:fs";
import { apiRequest } from "../lib/apiClient";
import { requireSession } from "../lib/tokenStore";
import { toResult } from "../lib/result";

interface OrdlakAskInput {
  message: string;
  conversationId?: number | null;
}

interface SaveReplyInput {
  /** Sugerowana nazwa pliku bez rozszerzenia - zwykle tytul rozmowy. */
  suggestedName: string;
  content: string;
}

/** Znaki zakazane w nazwie pliku na Windowsie - tytul rozmowy bywa dowolny. */
function toFileName(title: string): string {
  const cleaned = title.replace(/[\\/:*?"<>|]/g, "-").replace(/\s+/g, " ").trim();
  return (cleaned || "Raport Ordlaka").slice(0, 80);
}

export function registerOrdlakIpc(): void {
  ipcMain.handle("ordly:ordlak:status", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/ordlak/status");
    })
  );

  ipcMain.handle("ordly:ordlak:ask", async (_event, input: OrdlakAskInput) =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/ordlak/chat", {
        method: "POST",
        body: {
          message: input.message,
          conversation_id: input.conversationId ?? null,
        },
      });
    })
  );

  ipcMain.handle("ordly:ordlak:conversations", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/ordlak/conversations");
    })
  );

  ipcMain.handle("ordly:ordlak:conversation", async (_event, id: number) =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(
        session.baseUrl,
        session.token,
        `/api/v1/ordlak/conversations/${encodeURIComponent(String(id))}`
      );
    })
  );

  ipcMain.handle("ordly:ordlak:deleteConversation", async (_event, id: number) =>
    toResult(async () => {
      const session = requireSession();
      await apiRequest(
        session.baseUrl,
        session.token,
        `/api/v1/ordlak/conversations/${encodeURIComponent(String(id))}`,
        { method: "DELETE" }
      );
      return null;
    })
  );

  ipcMain.handle("ordly:ordlak:saveReply", async (_event, input: SaveReplyInput) =>
    toResult(async () => {
      const win = BrowserWindow.getFocusedWindow();
      const options: Electron.SaveDialogOptions = {
        title: "Zapisz odpowiedź Ordlaka",
        defaultPath: `${toFileName(input.suggestedName)}.md`,
        filters: [
          { name: "Markdown", extensions: ["md"] },
          { name: "Plik tekstowy", extensions: ["txt"] },
        ],
      };
      const result = win
        ? await dialog.showSaveDialog(win, options)
        : await dialog.showSaveDialog(options);
      if (result.canceled || !result.filePath) {
        return { saved: false, path: null };
      }
      // BOM - inaczej Notatnik w polskiej lokalizacji pokazuje krzaki
      // zamiast ogonków, tak samo jak przy eksporcie CSV zamówień.
      writeFileSync(result.filePath, "﻿" + input.content, "utf-8");
      return { saved: true, path: result.filePath };
    })
  );
}
