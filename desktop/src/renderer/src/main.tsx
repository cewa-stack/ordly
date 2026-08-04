import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./lib/queryClient";
import { AuthProvider } from "./lib/auth";
import { ToastProvider } from "./lib/toast";
import { SyncProvider } from "./lib/sync";
import { App } from "./App";
import "./theme/global.css";

// Kolejnosc dostawcow nie jest dowolna: SyncProvider wola useToast
// i useQueryClient, wiec musi siedziec pod nimi obydwoma.
ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <SyncProvider>
            <App />
          </SyncProvider>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
