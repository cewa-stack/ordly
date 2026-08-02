import { BrowserWindow, dialog, ipcMain } from "electron";
import { readFileSync } from "node:fs";
import { type OlxOffer, deleteOlxOffer, listOlxOffers, saveOlxOffer } from "../lib/olxStore";
import { parseOlxCsv } from "../lib/olxCsv";

export function registerOlxIpc(): void {
  ipcMain.handle("ordly:olx:list", () => listOlxOffers());

  ipcMain.handle("ordly:olx:save", (_event, input: Omit<OlxOffer, "id"> & { id?: string }) =>
    saveOlxOffer(input)
  );

  ipcMain.handle("ordly:olx:delete", (_event, id: string) => {
    deleteOlxOffer(id);
  });

  ipcMain.handle("ordly:olx:importCsv", async () => {
    const win = BrowserWindow.getFocusedWindow();
    const options: Electron.OpenDialogOptions = {
      title: "Importuj oferty OLX z pliku CSV",
      filters: [{ name: "CSV", extensions: ["csv"] }],
      properties: ["openFile"],
    };
    const dialogResult = win
      ? await dialog.showOpenDialog(win, options)
      : await dialog.showOpenDialog(options);
    if (dialogResult.canceled || dialogResult.filePaths.length === 0) {
      return { imported: 0, cancelled: true };
    }
    const content = readFileSync(dialogResult.filePaths[0], "utf-8");
    const rows = parseOlxCsv(content);
    for (const row of rows) {
      saveOlxOffer(row);
    }
    return { imported: rows.length, cancelled: false };
  });
}
