/**
 * Typy odpowiedzi ORDLY API - lustro `app/api/schemas.py` w backendzie.
 * Jeśli zmienia się kształt odpowiedzi API, ten plik i schemas.py mają
 * się zmieniać razem (jedno źródło prawdy to backend - ten plik go tylko
 * odzwierciedla po stronie klienta).
 */

/**
 * Kwota w JSON-ie z API. Backend serializuje `Decimal` przez alias
 * `Money` (schemas.py) jako LICZBE - wczesniej pydantic oddawal string,
 * przez co dodawanie kwot w JS sklejalo teksty zamiast sumowac.
 * `formatMoney` przyjmuje oba warianty, wiec starszy backend na Pi
 * dalej sie wyswietli poprawnie.
 */
export type Money = number;

export interface OrderProduct {
  external_id: string;
  name: string;
  quantity: number;
  unit_price: Money;
  total_price: Money;
}

export interface Order {
  external_id: string;
  marketplace: string;
  buyer_login: string;
  total_amount: Money;
  currency: string;
  status: string;
  fulfillment_status: string | null;
  tracking_number: string | null;
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

/**
 * Oferta wystawiona na marketplace - jedna pozycja Magazynu.
 *
 * `available_stock` przychodzi z API marketplace i mówi, ile sztuk
 * obiecuje oferta kupującym. `quantity_on_hand` wpisuje się ręcznie
 * na desktopie i mówi, ile ich naprawdę leży na półce; `null` znaczy
 * "nigdy nie liczono" i nie jest tym samym co 0.
 */
export interface MarketplaceOffer {
  marketplace: string;
  external_id: string;
  name: string;
  signature: string | null;
  status: string;
  available_stock: number;
  sold_count: number;
  price: Money | null;
  image_url: string | null;
  synced_at: string | null;
  quantity_on_hand: number | null;
}

export interface CatalogSync {
  marketplace: string;
  fetched: number;
  added: number;
  removed: number;
  synced_at: string;
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

export type MailSource = "allegro" | "allegro_lokalnie" | "olx" | "other";

export interface MailMessage {
  message_id: string;
  sender: string;
  subject: string;
  received_at: string;
  source: MailSource;
  body_preview: string;
  is_read: boolean;
}

/**
 * Pełna treść maila, dociągana ze skrzynki dopiero przy otwarciu
 * wiadomości - w bazie na Pi leżą wyłącznie metadane i krótki podgląd.
 *
 * `html_body` renderuje się w izolowanej ramce (PWA), `plain_body` jest
 * wariantem zapasowym. Backend gwarantuje, że `plain_body` nie jest
 * puste, jeśli mail ma jakąkolwiek treść (patrz `mail_body_out`).
 */
export interface MailBody {
  html_body: string | null;
  plain_body: string | null;
}

/**
 * Asystent Ordlak. Kształt 1:1 z `app/api/schemas.py` na Pi -
 * `POST /api/v1/ordlak/chat` istnieje od czasu desktopu, więc telefon
 * nie potrzebuje nowego endpointu, tylko go woła.
 */
export interface OrdlakStatus {
  configured: boolean;
  model: string;
}

export interface OrdlakChatReply {
  conversation_id: number;
  reply: string;
  /** Narzędzia, z których model odczytał dane - pokazywane pod odpowiedzią. */
  used_tools: string[];
}

export interface OrdlakStoredMessage {
  role: "user" | "assistant";
  content: string;
  created_at: string;
  used_tools: string[];
}

/**
 * Wątek rozmowy. Na LIŚCIE `messages` jest puste - pełną historię oddaje
 * dopiero pobranie pojedynczego wątku.
 */
export interface OrdlakConversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  messages: OrdlakStoredMessage[];
}
