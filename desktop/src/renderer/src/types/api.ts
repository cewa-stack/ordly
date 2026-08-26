/**
 * Ksztalt danych 1:1 z app/api/schemas.py (backend ORDLY). Renderer
 * deklaruje te typy niezaleznie od main procesu - IPC i tak przenosi
 * tylko zwykly JSON, wiec nie ma wspolnych klas do dzielenia miedzy
 * procesami.
 */

export type StockStatus = "ok" | "warning" | "critical";

export interface StockItem {
  sku: string;
  name: string;
  stock: number;
  min_stock: number;
  max_stock: number | null;
  ean: string | null;
  category: string | null;
  location: string | null;
  purchase_cost: number | null;
  sale_price: number | null;
  stock_value: number;
  is_low_stock: boolean;
  status: StockStatus;
  /**
   * SKU produktu glownego, jesli ten produkt jest podproduktem.
   * Lista magazynowa pokazuje tylko wiersze z `null` - podprodukty
   * chowaja sie pod produktem glownym, po rozwinieciu.
   */
  parent_sku: string | null;
}

export interface StockAdjustPayload {
  op: "set" | "add" | "remove" | "min";
  quantity: number;
  reason?: string;
}

export interface OrderProduct {
  external_id: string;
  name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

export interface Order {
  external_id: string;
  marketplace: string;
  buyer_login: string;
  total_amount: number;
  currency: string;
  status: string;
  fulfillment_status: string | null;
  order_date: string;
  products: OrderProduct[];
}

export interface SyncResult {
  new_orders_count: number;
  checked_orders_count: number;
  cancelled_orders_count: number;
  new_returns_count: number;
}

export interface ReturnItem {
  external_id: string;
  marketplace: string;
  order_external_id: string;
  buyer_login: string;
  status: string;
  products_summary: string;
  return_date: string;
}

export interface Issue {
  external_id: string;
  marketplace: string;
  type: "DISPUTE" | "CLAIM";
  status: string;
  order_external_id: string;
  buyer_login: string;
  subject: string | null;
  description: string | null;
  opened_at: string;
  messages_count: number;
  chat_active: boolean;
  last_message_at: string | null;
}

export interface IssueMessage {
  id: string;
  text: string;
  author_login: string;
  author_role: string;
  created_at: string;
}

export interface Session {
  baseUrl: string;
  username: string;
}

export interface Wholesaler {
  id: string;
  name: string;
  email: string;
  contactPerson?: string;
  linkedSkus: string[];
}

export interface WholesalerOrderRecord {
  id: string;
  wholesalerId: string;
  wholesalerName: string;
  sentAt: string;
  subject: string;
  itemsSummary: string;
}

export interface StatsSummary {
  orders_today: number;
  orders_this_month: number;
  revenue_today: number;
  revenue_this_month: number;
  total_orders: number;
}

export interface ItemForecast {
  sku: string;
  name: string;
  stock: number;
  avg_daily_sales: number;
  days_left: number;
}

export interface StockReport {
  total_items: number;
  total_stock_value: number;
  low_stock_items: StockItem[];
  items_without_sales: StockItem[];
  forecasts: ItemForecast[];
  recent_movements: unknown[];
}

export interface OlxOffer {
  id: string;
  title: string;
  price: number;
  stock: number;
  url: string;
  linkedSku?: string;
}

export interface MailMessage {
  message_id: string;
  sender: string;
  subject: string;
  received_at: string;
  source: "allegro" | "allegro_lokalnie" | "olx" | "other";
  body_preview: string;
  is_read: boolean;
}

/**
 * Pelna tresc maila, dociagana ze skrzynki dopiero przy otwarciu
 * wiadomosci - w bazie na Pi leza wylacznie metadane i krotki podglad.
 *
 * `html_body` idzie do izolowanego `<iframe>`, `plain_body` jest
 * wariantem zapasowym. Backend gwarantuje, ze `plain_body` nie jest
 * puste, jesli mail ma jakakolwiek tresc (patrz `mail_body_out`).
 */
export interface MailBody {
  html_body: string | null;
  plain_body: string | null;
}

/**
 * Stan skrzynki - pozwala odroznic "IMAP wylaczony na Pi" od
 * "wlaczony, ale nic nie przyszlo". Bez tego pusta lista maili byla
 * niema i wygladala jak awaria.
 */
export interface MailboxStatus {
  configured: boolean;
  host: string;
  user_masked: string;
  watch_senders: string[];
  message_count: number;
  last_received_at: string | null;
}

export interface MailSyncResult {
  new_count: number;
  configured: boolean;
}

/** Stan produktu w formularzu Ordlaka - te same kody co w backendzie. */
export type OrdlakCondition = "new" | "very_good" | "good" | "damaged";

/**
 * Rozbicie kalkulacji ceny. Prowizja Allegro liczy sie od sumy
 * `suggested_price + buyer_shipping_cost`, nie od samej ceny - dlatego
 * `commission_amount` przychodzi z backendu gotowe, a nie jest liczone w UI.
 */
export interface OrdlakPriceBreakdown {
  purchase_cost: number;
  inbound_shipping_cost: number;
  buyer_shipping_cost: number;
  commission_percent: number;
  target_margin_percent: number;
  commission_amount: number;
  suggested_price: number;
}

export interface OrdlakGeneration {
  id: number;
  created_at: string;
  title: string;
  description_html: string;
  condition_notes: string | null;
  condition: OrdlakCondition;
  photo_count: number;
  /** true = tytul jest regulaminowo poprawny, ale ponizej celu SEO (65+ znakow). */
  title_below_target: boolean;
  price_breakdown: OrdlakPriceBreakdown;
}

export interface OrdlakHistoryItem {
  id: number;
  created_at: string;
  title: string;
  description_html: string;
  condition_notes: string | null;
  condition: OrdlakCondition;
  photo_count: number;
  user_note: string;
  is_edited: boolean;
  price_breakdown: OrdlakPriceBreakdown;
}

export interface OrdlakStatus {
  configured: boolean;
  model: string;
  max_photos: number;
  max_photo_size_mb: number;
}

export interface OrdlakPhotoPayload {
  fileName: string;
  mimeType: string;
  bytes: Uint8Array;
}

export interface OrdlakGeneratePayload {
  note: string;
  condition: OrdlakCondition;
  purchaseCost: number;
  inboundShippingCost: number;
  buyerShippingCost: number;
  commissionPercent: number;
  targetMarginPercent: number;
  photos?: OrdlakPhotoPayload[];
}

export interface DashboardSummary {
  orders_today: number;
  revenue_today: number;
  orders_to_ship: number;
  low_stock_count: number;
  revenue_last_7_days: number[];
  trend_percent: number;
  last_sync_human: string;
  marketplace_connection_ok: boolean;
}

export interface HealthStatus {
  uptime: string;
  last_sync: string;
  database_ok: boolean;
  marketplace_connection_ok: boolean;
}

export interface SystemEvent {
  event_type: string;
  level: string;
  created_at: string;
}

export interface StockMovement {
  item_sku: string;
  item_name: string;
  change: number;
  stock_after: number;
  reason: string;
  source: string;
  reference: string | null;
  occurred_at: string;
}

export interface RecipeComponent {
  sku: string;
  name: string;
  quantity: number;
}

export interface OfferRecipe {
  marketplace: string;
  external_product_id: string;
  offer_name: string | null;
  components: RecipeComponent[];
}

export interface UnmappedOffer {
  marketplace: string;
  external_product_id: string;
  name: string;
  sold_quantity: number;
  orders_count: number;
  last_sold_at: string;
}

export interface OfferRecipePayload {
  components: { sku: string; quantity: number }[];
}

export interface OfferRef {
  marketplace: string;
  externalProductId: string;
}

export interface BackfillLine {
  order_external_id: string;
  order_date: string;
  quantity: number;
  already_applied: boolean;
}

export interface BackfillComponent {
  sku: string;
  name: string;
  current_stock: number;
  quantity: number;
  stock_after: number;
}

export interface BackfillPlan {
  marketplace: string;
  external_product_id: string;
  offer_name: string | null;
  since: string;
  applied: boolean;
  pending_quantity: number;
  lines: BackfillLine[];
  components: BackfillComponent[];
}

export interface StockCreatePayload {
  sku: string;
  name: string;
  min_stock: number;
}

export interface Shipment {
  order_external_id: string;
  carrier: string | null;
  tracking_number: string | null;
  status: string;
}

export interface WholesalerOrderSendPayload {
  wholesalerId: string;
  wholesalerName: string;
  to: string;
  subject: string;
  body: string;
  itemsSummary: string;
}

export type BridgeResult<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; message: string };
