import type {
  BridgeResult,
  Issue,
  IssueMessage,
  MailMessage,
  OlxOffer,
  Order,
  ReturnItem,
  Session,
  StatsSummary,
  StockAdjustPayload,
  StockItem,
  StockReport,
  SyncResult,
  Wholesaler,
  WholesalerOrderRecord,
  WholesalerOrderSendPayload,
} from "./api";

export interface OrdlyBridge {
  auth: {
    getSession: () => Promise<Session | null>;
    login: (
      baseUrl: string,
      username: string,
      password: string
    ) => Promise<BridgeResult<Session>>;
    logout: () => Promise<void>;
  };
  stock: {
    list: () => Promise<BridgeResult<StockItem[]>>;
    adjust: (sku: string, payload: StockAdjustPayload) => Promise<BridgeResult<StockItem>>;
  };
  orders: {
    list: () => Promise<BridgeResult<Order[]>>;
    sync: () => Promise<BridgeResult<SyncResult>>;
  };
  returns: {
    list: () => Promise<BridgeResult<ReturnItem[]>>;
  };
  issues: {
    list: () => Promise<BridgeResult<Issue[]>>;
    messages: (issueId: string) => Promise<BridgeResult<IssueMessage[]>>;
    reply: (issueId: string, text: string) => Promise<BridgeResult<null>>;
  };
  stats: {
    get: () => Promise<BridgeResult<StatsSummary>>;
    stockReport: () => Promise<BridgeResult<StockReport>>;
    shoppingList: () => Promise<BridgeResult<StockItem[]>>;
  };
  olx: {
    list: () => Promise<OlxOffer[]>;
    save: (input: Omit<OlxOffer, "id"> & { id?: string }) => Promise<OlxOffer>;
    delete: (id: string) => Promise<void>;
    importCsv: () => Promise<{ imported: number; cancelled: boolean }>;
  };
  mailbox: {
    list: (filters: {
      source?: "allegro" | "olx" | "other";
      unreadOnly?: boolean;
    }) => Promise<BridgeResult<MailMessage[]>>;
    markRead: (messageId: string) => Promise<BridgeResult<null>>;
  };
  wholesalers: {
    list: () => Promise<Wholesaler[]>;
    save: (input: Omit<Wholesaler, "id"> & { id?: string }) => Promise<Wholesaler>;
    delete: (id: string) => Promise<void>;
    history: () => Promise<WholesalerOrderRecord[]>;
    sendOrder: (payload: WholesalerOrderSendPayload) => Promise<BridgeResult<null>>;
  };
  window: {
    minimize: () => Promise<void>;
    maximize: () => Promise<void>;
    close: () => Promise<void>;
  };
}

declare global {
  interface Window {
    ordly: OrdlyBridge;
  }
}
