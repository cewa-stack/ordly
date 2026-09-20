/**
 * Punkt wejscia PODGLADU UKLADU. Montuje prawdziwy ShellLayout z prawdziwymi
 * dostawcami - rozni sie od aplikacji wylacznie atrapa `window.ordly`.
 */
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { installMockBridge } from "./mockBridge";

installMockBridge();

import { queryClient } from "../src/renderer/src/lib/queryClient";
import { ToastProvider } from "../src/renderer/src/lib/toast";
import { SyncProvider } from "../src/renderer/src/lib/sync";
import { OrdlakStateProvider } from "../src/renderer/src/lib/ordlakState";
import { ShellLayout } from "../src/renderer/src/screens/ShellLayout";
import { AuthProvider } from "../src/renderer/src/lib/auth";
import "../src/renderer/src/theme/global.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <SyncProvider>
            <OrdlakStateProvider>
              <ShellLayout />
            </OrdlakStateProvider>
          </SyncProvider>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
