import type {
  BridgeResult,
  DashboardSummary,
  HealthStatus,
  Issue,
  IssueMessage,
  MailboxStatus,
  MailMessage,
  MailSyncResult,
  OlxOffer,
  Order,
  ReturnItem,
  Session,
  Shipment,
  StatsSummary,
  StockAdjustPayload,
  StockCreatePayload,
  StockItem,
  StockMovement,
  StockReport,
  SyncResult,
  SystemEvent,
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
    create: (payload: StockCreatePayload) => Promise<BridgeResult<StockItem>>;
    history: (sku: string) => Promise<BridgeResult<StockMovement[]>>;
    adjust: (sku: string, payload: StockAdjustPayload) => Promise<BridgeResult<StockItem>>;
  };
  orders: {
    list: () => Promise<BridgeResult<Order[]>>;
    search: (query: string) => Promise<BridgeResult<Order[]>>;
    tracking: (externalId: string) => Promise<BridgeResult<Shipment>>;
    setFulfillment: (
      externalId: string,
      status: "NEW" | "PROCESSING" | "READY_FOR_SHIPMENT" | "SENT" | "PICKED_UP"
    ) => Promise<BridgeResult<Order>>;
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
    dashboard: () => Promise<BridgeResult<DashboardSummary>>;
    health: () => Promise<BridgeResult<HealthStatus>>;
    events: () => Promise<BridgeResult<SystemEvent[]>>;
    backup: () => Promise<BridgeResult<{ status: string; backup_path: string }>>;
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
    status: () => Promise<BridgeResult<MailboxStatus>>;
    sync: () => Promise<BridgeResult<MailSyncResult>>;
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
