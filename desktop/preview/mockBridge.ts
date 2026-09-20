/**
 * Atrapa mostka `window.ordly` do PODGLADU UKLADU (npm run preview:ui).
 *
 * Nie jest czescia aplikacji i nie wchodzi do bundla produkcyjnego -
 * mieszka poza `src/`, ma wlasna konfiguracje Vite i sluzy wylacznie do
 * ogladania ekranow w przegladarce bez Raspberry Pi.
 *
 * Dane sa zmyslone CELOWO i tylko tutaj. Ich ksztalt jest przepisany
 * z `src/renderer/src/types/api.ts`, wiec podglad lamie sie dokladnie
 * tam, gdzie zlamalaby sie prawdziwa aplikacja.
 */
import type { OrdlyBridge } from "../src/renderer/src/types/ordly-bridge";
import type { Order } from "../src/renderer/src/types/api";

const ok = <T,>(data: T) => Promise.resolve({ ok: true as const, data });

function hoursAgo(hours: number): string {
  return new Date(Date.now() - hours * 3_600_000).toISOString();
}

const ORDERS: Order[] = [
  {
    external_id: "a1f3c92e-7b41-4d2a-9c11-004fd2a81b77",
    marketplace: "allegro",
    buyer_login: "marta_kowalska",
    total_amount: 249.9,
    currency: "PLN",
    status: "READY_FOR_PROCESSING",
    fulfillment_status: "NEW",
    tracking_number: null,
    order_date: hoursAgo(2),
    products: [
      {
        external_id: "off-1",
        name: "Świeca sojowa Bergamotka 220 ml",
        quantity: 2,
        unit_price: 79.9,
        total_price: 159.8,
      },
      {
        external_id: "off-2",
        name: "Dyfuzor zapachowy Cedr",
        quantity: 1,
        unit_price: 90.1,
        total_price: 90.1,
      },
    ],
  },
  {
    external_id: "b2d4e81f-3312-4aa7-8bd0-91ce4477a002",
    marketplace: "allegro_lokalnie",
    buyer_login: "pawel.nowicki",
    total_amount: 89,
    currency: "PLN",
    status: "READY_FOR_PROCESSING",
    fulfillment_status: "NEW",
    tracking_number: null,
    order_date: hoursAgo(28),
    products: [
      {
        external_id: "off-3",
        name: "Zestaw podgrzewaczy 20 szt.",
        quantity: 1,
        unit_price: 89,
        total_price: 89,
      },
    ],
  },
  {
    external_id: "c3a5f770-9021-41be-a3c8-55de17bb9931",
    marketplace: "olx",
    buyer_login: "anna-wisniewska-1988",
    total_amount: 1240.5,
    currency: "PLN",
    status: "PROCESSING",
    fulfillment_status: "PROCESSING",
    tracking_number: "640123456789012345",
    order_date: hoursAgo(5),
    products: [
      {
        external_id: "off-4",
        name: "Lampa stołowa mosiądz, klosz lniany, edycja limitowana",
        quantity: 1,
        unit_price: 1240.5,
        total_price: 1240.5,
      },
    ],
  },
  {
    external_id: "d4b60881-1177-4c33-90aa-7731cc22ee10",
    marketplace: "amazon",
    buyer_login: "t.zielinski",
    total_amount: 59.99,
    currency: "PLN",
    status: "READY_FOR_PROCESSING",
    fulfillment_status: "READY_FOR_SHIPMENT",
    tracking_number: null,
    order_date: hoursAgo(9),
    products: [
      {
        external_id: "off-5",
        name: "Wosk zapachowy Wanilia",
        quantity: 3,
        unit_price: 19.99,
        total_price: 59.97,
      },
    ],
  },
  {
    external_id: "e5c71992-2288-4d44-a1bb-8842dd33ff21",
    marketplace: "allegro",
    buyer_login: "k_lewandowski",
    total_amount: 420,
    currency: "PLN",
    status: "READY_FOR_PROCESSING",
    fulfillment_status: "SENT",
    tracking_number: "640987654321098765",
    order_date: hoursAgo(30),
    products: [
      {
        external_id: "off-6",
        name: "Zestaw prezentowy Zima",
        quantity: 2,
        unit_price: 210,
        total_price: 420,
      },
    ],
  },
  {
    external_id: "f6d82aa3-3399-4e55-b2cc-9953ee44aa32",
    marketplace: "allegro",
    buyer_login: "sklep.dekoracje24",
    total_amount: 3120,
    currency: "PLN",
    status: "CANCELLED",
    fulfillment_status: "CANCELLED",
    tracking_number: null,
    order_date: hoursAgo(50),
    products: [
      {
        external_id: "off-7",
        name: "Paleta świec mix 120 szt.",
        quantity: 1,
        unit_price: 3120,
        total_price: 3120,
      },
    ],
  },
];

export function installMockBridge(): void {
  const bridge = {
    auth: {
      getSession: () => Promise.resolve({ baseUrl: "http://ordly-pi:8000", username: "lukas" }),
      login: () => ok({ baseUrl: "http://ordly-pi:8000", username: "lukas" }),
      logout: () => Promise.resolve(),
    },
    stock: {
      offers: () =>
        ok([
          {
            marketplace: "allegro",
            external_id: "off-1",
            name: "Świeca sojowa Bergamotka 220 ml",
            signature: null,
            status: "ACTIVE",
            available_stock: 12,
            sold_count: 48,
            price: 79.9,
            image_url: null,
            synced_at: hoursAgo(1),
            quantity_on_hand: 4,
          },
          {
            marketplace: "allegro",
            external_id: "off-2",
            name: "Dyfuzor zapachowy Cedr",
            signature: null,
            status: "ACTIVE",
            available_stock: 6,
            sold_count: 11,
            price: 90.1,
            image_url: null,
            synced_at: hoursAgo(1),
            quantity_on_hand: 9,
          },
          {
            marketplace: "olx",
            external_id: "off-4",
            name: "Lampa stołowa mosiądz",
            signature: null,
            status: "ACTIVE",
            available_stock: 2,
            sold_count: 1,
            price: 1240.5,
            image_url: null,
            synced_at: hoursAgo(3),
            quantity_on_hand: null,
          },
        ]),
      sync: () =>
        ok({
          marketplace: "allegro",
          fetched: 3,
          added: 0,
          removed: 0,
          synced_at: hoursAgo(0),
        }),
      setQuantity: () => ok(null),
      history: () => ok([]),
    },
    orders: {
      list: () => ok(ORDERS),
      search: () => ok(ORDERS),
      tracking: (externalId: string) =>
        ok({
          order_external_id: externalId,
          carrier: "InPost",
          tracking_number:
            ORDERS.find((order) => order.external_id === externalId)?.tracking_number ?? null,
          status: "IN_TRANSIT",
        }),
      setFulfillment: () => ok(ORDERS[0]),
      sync: () =>
        ok({
          new_orders_count: 2,
          checked_orders_count: 18,
          cancelled_orders_count: 0,
          new_returns_count: 0,
        }),
    },
    returns: {
      list: () =>
        ok([
          {
            external_id: "ret-1",
            marketplace: "allegro",
            order_external_id: ORDERS[0].external_id,
            buyer_login: "marta_kowalska",
            status: "CREATED",
            products_summary: "Świeca sojowa Bergamotka",
            return_date: hoursAgo(6),
          },
        ]),
    },
    issues: {
      list: () =>
        ok([
          {
            external_id: "iss-1",
            marketplace: "allegro",
            type: "DISPUTE" as const,
            status: "DISPUTE_ONGOING",
            order_external_id: ORDERS[0].external_id,
            buyer_login: "marta_kowalska",
            subject: "Uszkodzone opakowanie",
            description: null,
            opened_at: hoursAgo(4),
            messages_count: 3,
            chat_active: true,
            last_message_at: hoursAgo(1),
          },
          {
            external_id: "iss-2",
            marketplace: "olx",
            type: "CLAIM" as const,
            status: "CLAIM_SUBMITTED",
            order_external_id: ORDERS[2].external_id,
            buyer_login: "anna-wisniewska-1988",
            subject: "Gdzie paczka?",
            description: null,
            opened_at: hoursAgo(20),
            messages_count: 1,
            chat_active: true,
            last_message_at: hoursAgo(20),
          },
        ]),
      messages: () => ok([]),
      reply: () => ok(null),
    },
    stats: {
      get: () =>
        ok({
          orders_today: 7,
          orders_this_month: 118,
          revenue_today: 2340,
          revenue_this_month: 38120,
          total_orders: 1422,
        }),
      dashboard: () =>
        ok({
          orders_today: 7,
          revenue_today: 2340,
          orders_to_ship: 3,
          revenue_last_7_days: [1820, 2410, 1190, 3050, 2680, 1975, 2340],
          trend_percent: 12,
          last_sync_human: "2 min temu",
          marketplace_connection_ok: true,
        }),
      health: () =>
        ok({
          uptime: "6 dni",
          last_sync: hoursAgo(0),
          database_ok: true,
          marketplace_connection_ok: true,
        }),
      events: () =>
        ok([
          { event_type: "OrderCreated", level: "INFO", created_at: hoursAgo(0.3) },
          { event_type: "DisputeNoticeDetected", level: "WARNING", created_at: hoursAgo(1.2) },
          { event_type: "AllegroLokalnieEventDetected", level: "INFO", created_at: hoursAgo(2.6) },
          { event_type: "OrderReturnCreated", level: "INFO", created_at: hoursAgo(5.1) },
          { event_type: "OrderCancelled", level: "WARNING", created_at: hoursAgo(7.4) },
        ]),
      backup: () => ok({ status: "ok", backup_path: "/home/pi/backups/ordly.db" }),
    },
    olx: {
      list: () => Promise.resolve([]),
      save: (input: unknown) => Promise.resolve(input),
      delete: () => Promise.resolve(),
      importCsv: () => Promise.resolve({ imported: 0, cancelled: true }),
    },
    mailbox: {
      list: () =>
        ok([
          {
            message_id: "m1",
            sender: "powiadomienia@allegromail.pl",
            subject: "Masz nowe zamówienie w Allegro Lokalnie",
            received_at: hoursAgo(1),
            source: "allegro_lokalnie" as const,
            body_preview: "Kupujący pawel.nowicki złożył zamówienie…",
            is_read: false,
          },
          {
            message_id: "m2",
            sender: "noreply@olx.pl",
            subject: "Nowa wiadomość do Twojego ogłoszenia",
            received_at: hoursAgo(3),
            source: "olx" as const,
            body_preview: "Dzień dobry, czy lampa jest jeszcze dostępna?",
            is_read: false,
          },
        ]),
      status: () =>
        ok({
          configured: true,
          host: "imap.gmail.com",
          user_masked: "s***@gmail.com",
          watch_senders: ["allegromail.pl", "olx.pl"],
          message_count: 42,
          last_received_at: hoursAgo(1),
        }),
      sync: () => ok({ new_count: 1, configured: true }),
      body: () => ok({ html_body: null, plain_body: "Treść wiadomości." }),
      markRead: () => ok(null),
    },
    ordlak: {
      status: () => ok({ configured: true, model: "claude-sonnet-5" }),
      ask: (input: { message: string }) =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                data: {
                  conversation_id: 1,
                  reply: `Podgląd układu — pytanie brzmiało: „${input.message}". W prawdziwej aplikacji odpowiada model na Pi.`,
                  used_tools: ["podsumowanie_sprzedazy"],
                },
              }),
            1400
          )
        ),
      conversations: () => ok([]),
      conversation: () => ok({ id: 1, title: "Podgląd", created_at: hoursAgo(1), updated_at: hoursAgo(1), message_count: 0, messages: [] }),
      deleteConversation: () => ok(null),
      saveReply: () => ok({ saved: false, path: null }),
    },
    wholesalers: {
      list: () => Promise.resolve([]),
      save: (input: unknown) => Promise.resolve(input),
      delete: () => Promise.resolve(),
      history: () => Promise.resolve([]),
      sendOrder: () => ok(null),
    },
    window: {
      minimize: () => Promise.resolve(),
      maximize: () => Promise.resolve(),
      close: () => Promise.resolve(),
    },
  };

  (window as unknown as { ordly: OrdlyBridge }).ordly = bridge as unknown as OrdlyBridge;
}
