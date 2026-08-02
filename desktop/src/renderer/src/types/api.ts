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
  source: "allegro" | "olx" | "other";
  body_preview: string;
  is_read: boolean;
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
