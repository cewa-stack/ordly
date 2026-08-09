/**
 * Typy odpowiedzi ORDLY API - lustro `app/api/schemas.py` w backendzie.
 * Jeśli zmienia się kształt odpowiedzi API, ten plik i schemas.py mają
 * się zmieniać razem (jedno źródło prawdy to backend - ten plik go tylko
 * odzwierciedla po stronie klienta).
 */

export type StockStatus = "ok" | "warning" | "critical";

export interface OrderProduct {
  external_id: string;
  name: string;
  quantity: number;
  unit_price: string;
  total_price: string;
}

export interface Order {
  external_id: string;
  marketplace: string;
  buyer_login: string;
  total_amount: string;
  currency: string;
  status: string;
  fulfillment_status: string | null;
  order_date: string;
  products: OrderProduct[];
}

export interface Shipment {
  order_external_id: string;
  carrier: string | null;
  tracking_number: string | null;
  status: string | null;
  updated_at: string | null;
}

export interface SyncResult {
  new_orders_count: number;
  checked_orders_count: number;
  cancelled_orders_count: number;
  new_returns_count: number;
}

export interface StockItem {
  sku: string;
  name: string;
  stock: number;
  min_stock: number;
  max_stock: number | null;
  ean: string | null;
  category: string | null;
  location: string | null;
  purchase_cost: string | null;
  sale_price: string | null;
  stock_value: string;
  is_low_stock: boolean;
  status: StockStatus;
}

export type StockAdjustOp = "set" | "add" | "remove" | "min";

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

export interface ItemForecast {
  sku: string;
  name: string;
  stock: number;
  avg_daily_sales: number;
  days_left: number;
}

export interface StockReport {
  total_items: number;
  total_stock_value: string;
  low_stock_items: StockItem[];
  items_without_sales: StockItem[];
  forecasts: ItemForecast[];
  recent_movements: StockMovement[];
}

export interface UnmappedOffer {
  marketplace: string;
  external_product_id: string;
  name: string;
  sold_quantity: number;
  orders_count: number;
  last_sold_at: string;
}

export interface Stats {
  orders_today: number;
  orders_this_month: number;
  revenue_today: number;
  revenue_this_month: number;
  total_orders: number;
}

export interface Health {
  uptime: string;
  last_sync: string;
  database_ok: boolean;
  marketplace_connection_ok: boolean;
}

export interface Dashboard {
  orders_today: number;
  revenue_today: number;
  orders_to_ship: number;
  low_stock_count: number;
  revenue_last_7_days: number[];
  trend_percent: number | null;
  last_sync_human: string;
  marketplace_connection_ok: boolean;
}

export interface EventLog {
  event_type: string;
  level: string;
  created_at: string;
}

export interface VapidStatus {
  public_key: string;
  enabled: boolean;
}

export interface PushSubscribeBody {
  endpoint: string;
  keys: { p256dh: string; auth: string };
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

export type IssueType = "DISPUTE" | "CLAIM";

export interface Issue {
  external_id: string;
  marketplace: string;
  type: IssueType;
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

export type MailSource = "allegro" | "olx" | "other";

export interface MailMessage {
  message_id: string;
  sender: string;
  subject: string;
  received_at: string;
  source: MailSource;
  body_preview: string;
  is_read: boolean;
}
