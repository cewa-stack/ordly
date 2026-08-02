import { app, BrowserWindow, ipcMain, shell } from "electron";
import { join } from "node:path";
import { registerAuthIpc } from "./ipc/auth";
import { registerStockIpc } from "./ipc/stock";
import { registerOrdersIpc } from "./ipc/orders";
import { registerReturnsIpc } from "./ipc/returns";
import { registerIssuesIpc } from "./ipc/issues";
import { registerWholesalersIpc } from "./ipc/wholesalers";
import { registerMailboxIpc } from "./ipc/mailbox";
import { registerOlxIpc } from "./ipc/olx";
import { registerStatsIpc } from "./ipc/stats";

/**
 * Okno jest bezramkowe (`frame: false`) - wlasny pasek tytulowy w
 * rendererze (patrz Titlebar.tsx) rysuje minimalistyczne przyciski
 * min/maks/zamknij zgodne z paleta ORDLY zamiast natywnego chromu
 * Windows. Te trzy handlery dzialaja na aktualnie skupionym oknie,
 * zeby rejestracja ipcMain.handle nie powtarzala sie przy kazdym
 * createWindow() (Electron rzuca bledem przy podwojnej rejestracji).
 */
function registerWindowControlsIpc(): void {
  ipcMain.handle("ordly:window:minimize", () => {
    BrowserWindow.getFocusedWindow()?.minimize();
  });
  ipcMain.handle("ordly:window:maximize", () => {
    const win = BrowserWindow.getFocusedWindow();
    if (!win) return;
    if (win.isMaximized()) {
      win.unmaximize();
    } else {
      win.maximize();
    }
  });
  ipcMain.handle("ordly:window:close", () => {
    BrowserWindow.getFocusedWindow()?.close();
  });
}

function createWindow(): void {
  const win = new BrowserWindow({
    width: 1200,
    height: 780,
    minWidth: 880,
    minHeight: 600,
    show: false,
    frame: false,
    backgroundColor: "#0d1117",
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.on("ready-to-show", () => win.show());

  win.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url);
    return { action: "deny" };
  });

  const devServerUrl = process.env["ELECTRON_RENDERER_URL"];
  if (devServerUrl) {
    void win.loadURL(devServerUrl);
  } else {
    void win.loadFile(join(__dirname, "../renderer/index.html"));
  }
}

app.whenReady().then(() => {
  registerWindowControlsIpc();
  registerAuthIpc();
  registerStockIpc();
  registerOrdersIpc();
  registerReturnsIpc();
  registerIssuesIpc();
  registerWholesalersIpc();
  registerMailboxIpc();
  registerOlxIpc();
  registerStatsIpc();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
