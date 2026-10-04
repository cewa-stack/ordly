import type {
  CaseQuery,
  CaseReasonChange,
  CaseUpdate,
  CustomerCase,
  AppStatus,
  BridgeResult,
  CatalogSyncResult,
  DashboardSummary,
  HealthStatus,
  Issue,
  IssueMessage,
  MailBody,
  MailboxStatus,
  MailMessage,
  MailSyncResult,
  MarketplaceOffer,
  OfferMovement,
  OfferQuantityPayload,
  OfferRef,
  OlxOffer,
  OrdlakChatReply,
  OrdlakConversation,
  OrdlakSaveResult,
  OrdlakStatus,
  Order,
  OrderStatusChange,
  ReplyTemplate,
  ReplyTemplateInput,
  ReturnItem,
  Session,
  Shipment,
  StatsSummary,
  SyncResult,
  SystemEvent,
  Wholesaler,
  WholesalerOrderRecord,
  WholesalerOrderSendPayload,
  WholesalerTemplate,
  WholesalerTemplateInput,
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
    offers: () => Promise<BridgeResult<MarketplaceOffer[]>>;
    sync: () => Promise<BridgeResult<CatalogSyncResult>>;
    setQuantity: (
      offer: OfferRef,
      payload: OfferQuantityPayload
    ) => Promise<BridgeResult<MarketplaceOffer>>;
    history: (offer: OfferRef) => Promise<BridgeResult<OfferMovement[]>>;
  };
  orders: {
    list: () => Promise<BridgeResult<Order[]>>;
    search: (query: string) => Promise<BridgeResult<Order[]>>;
    get: (externalId: string) => Promise<BridgeResult<Order>>;
    tracking: (externalId: string) => Promise<BridgeResult<Shipment>>;
    setFulfillment: (
      externalId: string,
      status: "NEW" | "PROCESSING" | "READY_FOR_SHIPMENT" | "SENT" | "PICKED_UP"
    ) => Promise<BridgeResult<Order>>;
    /** Status aplikacyjny (tylko ORDLY); `null` = przywroc status z Allegro. */
    setAppStatus: (externalId: string, status: AppStatus | null) => Promise<BridgeResult<Order>>;
    appStatusHistory: (externalId: string) => Promise<BridgeResult<OrderStatusChange[]>>;
    sync: () => Promise<BridgeResult<SyncResult>>;
  };
  returns: {
    list: () => Promise<BridgeResult<ReturnItem[]>>;
  };
  /** Rejestr anulowan i zwrotow pieniedzy. */
  cases: {
    list: (query?: CaseQuery) => Promise<BridgeResult<CustomerCase[]>>;
    update: (id: number, update: CaseUpdate) => Promise<BridgeResult<CustomerCase>>;
    reasonHistory: (id: number) => Promise<BridgeResult<CaseReasonChange[]>>;
  };
  issues: {
    list: () => Promise<BridgeResult<Issue[]>>;
    messages: (issueId: string) => Promise<BridgeResult<IssueMessage[]>>;
    reply: (issueId: string, text: string) => Promise<BridgeResult<null>>;
  };
  templates: {
    list: () => Promise<BridgeResult<ReplyTemplate[]>>;
    create: (input: ReplyTemplateInput) => Promise<BridgeResult<ReplyTemplate>>;
    update: (id: number, input: ReplyTemplateInput) => Promise<BridgeResult<ReplyTemplate>>;
    delete: (id: number) => Promise<BridgeResult<null>>;
  };
  stats: {
    get: () => Promise<BridgeResult<StatsSummary>>;
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
    ask: (input: {
      message: string;
      conversationId?: number | null;
    }) => Promise<BridgeResult<OrdlakChatReply>>;
    apply: (input: {
      kind: string;
      params: Record<string, unknown>;
    }) => Promise<BridgeResult<{ message: string }>>;
    conversations: () => Promise<BridgeResult<OrdlakConversation[]>>;
    conversation: (id: number) => Promise<BridgeResult<OrdlakConversation>>;
    deleteConversation: (id: number) => Promise<BridgeResult<null>>;
    saveReply: (input: {
      suggestedName: string;
      content: string;
    }) => Promise<BridgeResult<OrdlakSaveResult>>;
  };
  wholesalers: {
    list: () => Promise<Wholesaler[]>;
    save: (input: Omit<Wholesaler, "id"> & { id?: string }) => Promise<Wholesaler>;
    delete: (id: string) => Promise<void>;
    history: () => Promise<WholesalerOrderRecord[]>;
    templates: () => Promise<WholesalerTemplate[]>;
    saveTemplate: (input: WholesalerTemplateInput) => Promise<WholesalerTemplate>;
    setDefaultTemplate: (id: string) => Promise<void>;
    deleteTemplate: (id: string) => Promise<void>;
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
