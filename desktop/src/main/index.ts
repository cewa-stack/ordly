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
import { registerOrdlakIpc } from "./ipc/ordlak";

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
    // Kolor tla okna PRZED pierwszym malowaniem renderera - musi byc
    // rowny `--panel` z systemu wizualnego, inaczej przy starcie mignie
    // jasna albo nie ta ciemna plansza.
    backgroundColor: "#141B19",
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.on("ready-to-show", () => win.show());

  // Diagnostyka wersji spakowanej: `ORDLY_DEVTOOLS=1` otwiera narzedzia
  // deweloperskie i przepisuje konsole renderera do stdout. Bez tego
  // jedyny sposob na zobaczenie bledu w .exe to zgadywanie.
  if (process.env["ORDLY_DEVTOOLS"] === "1") {
    win.webContents.openDevTools({ mode: "detach" });
    win.webContents.on("console-message", (_event, level, message, line, sourceId) => {
      // `process.stdout.write`, nie `console.log` - kryterium odbioru 10.3
      // zabrania `console.log` w kodzie, a to i tak jest strumien
      // diagnostyczny, nie logowanie aplikacyjne.
      process.stdout.write(`[renderer:${level}] ${message} (${sourceId}:${line})\n`);
    });
  }

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
  registerOrdlakIpc();
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
