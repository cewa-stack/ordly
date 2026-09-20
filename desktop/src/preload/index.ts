/**
 * Jedyny most miedzy rendererem a main procesem. Renderer nigdy nie
 * dostaje surowego tokenu ORDLY API - woła te metody, main proces
 * wykonuje realne żądanie HTTP z tokenem doklejonym po swojej stronie.
 */
import { contextBridge, ipcRenderer } from "electron";

const ordly = {
  auth: {
    getSession: () => ipcRenderer.invoke("ordly:auth:getSession"),
    login: (baseUrl: string, username: string, password: string) =>
      ipcRenderer.invoke("ordly:auth:login", baseUrl, username, password),
    logout: () => ipcRenderer.invoke("ordly:auth:logout"),
  },
  stock: {
    offers: () => ipcRenderer.invoke("ordly:stock:offers"),
    sync: () => ipcRenderer.invoke("ordly:stock:sync"),
    setQuantity: (
      offer: { marketplace: string; externalId: string },
      payload: { quantity: number; reason: string }
    ) => ipcRenderer.invoke("ordly:stock:setQuantity", offer, payload),
    history: (offer: { marketplace: string; externalId: string }) =>
      ipcRenderer.invoke("ordly:stock:history", offer),
  },
  orders: {
    list: () => ipcRenderer.invoke("ordly:orders:list"),
    search: (query: string) => ipcRenderer.invoke("ordly:orders:search", query),
    tracking: (externalId: string) => ipcRenderer.invoke("ordly:orders:tracking", externalId),
    setFulfillment: (externalId: string, status: string) =>
      ipcRenderer.invoke("ordly:orders:setFulfillment", externalId, status),
    sync: () => ipcRenderer.invoke("ordly:orders:sync"),
  },
  returns: {
    list: () => ipcRenderer.invoke("ordly:returns:list"),
  },
  issues: {
    list: () => ipcRenderer.invoke("ordly:issues:list"),
    messages: (issueId: string) => ipcRenderer.invoke("ordly:issues:messages", issueId),
    reply: (issueId: string, text: string) =>
      ipcRenderer.invoke("ordly:issues:reply", issueId, text),
  },
  stats: {
    get: () => ipcRenderer.invoke("ordly:stats:get"),
    dashboard: () => ipcRenderer.invoke("ordly:stats:dashboard"),
    health: () => ipcRenderer.invoke("ordly:stats:health"),
    events: () => ipcRenderer.invoke("ordly:stats:events"),
    backup: () => ipcRenderer.invoke("ordly:stats:backup"),
  },
  olx: {
    list: () => ipcRenderer.invoke("ordly:olx:list"),
    save: (input: {
      id?: string;
      title: string;
      price: number;
      stock: number;
      url: string;
      linkedSku?: string;
    }) => ipcRenderer.invoke("ordly:olx:save", input),
    delete: (id: string) => ipcRenderer.invoke("ordly:olx:delete", id),
    importCsv: () => ipcRenderer.invoke("ordly:olx:importCsv"),
  },
  mailbox: {
    list: (
      filters: {
        source?: "allegro" | "allegro_lokalnie" | "olx" | "other";
        unreadOnly?: boolean;
      } = {}
    ) =>
      ipcRenderer.invoke("ordly:mailbox:list", filters),
    status: () => ipcRenderer.invoke("ordly:mailbox:status"),
    sync: () => ipcRenderer.invoke("ordly:mailbox:sync"),
    body: (messageId: string) => ipcRenderer.invoke("ordly:mailbox:body", messageId),
    markRead: (messageId: string) => ipcRenderer.invoke("ordly:mailbox:markRead", messageId),
  },
  ordlak: {
    status: () => ipcRenderer.invoke("ordly:ordlak:status"),
    ask: (input: { message: string; conversationId?: number | null }) =>
      ipcRenderer.invoke("ordly:ordlak:ask", input),
    apply: (input: { kind: string; params: Record<string, unknown> }) =>
      ipcRenderer.invoke("ordly:ordlak:apply", input),
    conversations: () => ipcRenderer.invoke("ordly:ordlak:conversations"),
    conversation: (id: number) => ipcRenderer.invoke("ordly:ordlak:conversation", id),
    deleteConversation: (id: number) =>
      ipcRenderer.invoke("ordly:ordlak:deleteConversation", id),
    saveReply: (input: { suggestedName: string; content: string }) =>
      ipcRenderer.invoke("ordly:ordlak:saveReply", input),
  },
  wholesalers: {
    list: () => ipcRenderer.invoke("ordly:wholesalers:list"),
    save: (input: {
      id?: string;
      name: string;
      email: string;
      contactPerson?: string;
      items: { name: string; quantity: number }[];
    }) => ipcRenderer.invoke("ordly:wholesalers:save", input),
    delete: (id: string) => ipcRenderer.invoke("ordly:wholesalers:delete", id),
    history: () => ipcRenderer.invoke("ordly:wholesalers:history"),
    sendOrder: (payload: {
      wholesalerId: string;
      wholesalerName: string;
      to: string;
      subject: string;
      body: string;
      itemsSummary: string;
    }) => ipcRenderer.invoke("ordly:wholesalers:sendOrder", payload),
  },
  window: {
    minimize: () => ipcRenderer.invoke("ordly:window:minimize"),
    maximize: () => ipcRenderer.invoke("ordly:window:maximize"),
    close: () => ipcRenderer.invoke("ordly:window:close"),
  },
};

contextBridge.exposeInMainWorld("ordly", ordly);
