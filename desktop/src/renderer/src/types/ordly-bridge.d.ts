import type {
  BackfillPlan,
  BridgeResult,
  DashboardSummary,
  HealthStatus,
  Issue,
  IssueMessage,
  MailBody,
  MailboxStatus,
  MailMessage,
  MailSyncResult,
  OfferRecipe,
  OfferRecipePayload,
  OfferRef,
  OlxOffer,
  OrdlakGeneratePayload,
  OrdlakGeneration,
  OrdlakHistoryItem,
  OrdlakStatus,
  Order,
  ReturnItem,
  Session,
  Shipment,
  StatsSummary,
  StockAdjustPayload,
  StockCreatePayload,
  StockDeletion,
  StockItem,
  StockMovement,
  StockReport,
  SyncResult,
  SystemEvent,
  UnmappedOffer,
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
    remove: (sku: string) => Promise<BridgeResult<StockDeletion>>;
    history: (sku: string) => Promise<BridgeResult<StockMovement[]>>;
    adjust: (sku: string, payload: StockAdjustPayload) => Promise<BridgeResult<StockItem>>;
    subItems: (sku: string) => Promise<BridgeResult<StockItem[]>>;
    setParent: (sku: string, parentSku: string | null) => Promise<BridgeResult<StockItem>>;
    recipes: () => Promise<BridgeResult<OfferRecipe[]>>;
    unmappedOffers: () => Promise<BridgeResult<UnmappedOffer[]>>;
    setRecipe: (
      offer: OfferRef,
      payload: OfferRecipePayload
    ) => Promise<BridgeResult<OfferRecipe>>;
    deleteRecipe: (offer: OfferRef) => Promise<BridgeResult<{ removed: number }>>;
    previewBackfill: (offer: OfferRef) => Promise<BridgeResult<BackfillPlan>>;
    applyBackfill: (offer: OfferRef) => Promise<BridgeResult<BackfillPlan>>;
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
      source?: "allegro" | "allegro_lokalnie" | "olx" | "other";
      unreadOnly?: boolean;
    }) => Promise<BridgeResult<MailMessage[]>>;
    status: () => Promise<BridgeResult<MailboxStatus>>;
    sync: () => Promise<BridgeResult<MailSyncResult>>;
    body: (messageId: string) => Promise<BridgeResult<MailBody>>;
    markRead: (messageId: string) => Promise<BridgeResult<null>>;
  };
  ordlak: {
    status: () => Promise<BridgeResult<OrdlakStatus>>;
    generate: (payload: OrdlakGeneratePayload) => Promise<BridgeResult<OrdlakGeneration>>;
    history: (limit?: number) => Promise<BridgeResult<OrdlakHistoryItem[]>>;
    finalize: (input: {
      id: number;
      finalTitle: string;
      finalDescriptionHtml: string;
    }) => Promise<BridgeResult<OrdlakHistoryItem>>;
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
