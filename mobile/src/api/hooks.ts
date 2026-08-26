/**
 * Hooki react-query dla ORDLY API - jedno miejsce dla wszystkich wywołań
 * sieciowych używanych przez ekrany. Ekran nigdy nie woła `api.*`
 * bezpośrednio - zawsze przez hook stąd, żeby cache/retry/refetch był
 * spójny w całej aplikacji.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { api } from "./client";
import type {
  Dashboard,
  EventLog,
  Health,
  Issue,
  IssueMessage,
  MailBody,
  MailMessage,
  MailSource,
  Order,
  PushSubscribeBody,
  ReturnItem,
  Shipment,
  StockAdjustOp,
  StockItem,
  StockMovement,
  StockReport,
  SyncResult,
  UnmappedOffer,
  VapidStatus,
} from "./types";

// ---------------------------------------------------------------------
// Dashboard / zdrowie
// ---------------------------------------------------------------------

export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.get<Dashboard>("/api/v1/dashboard"),
    refetchInterval: 60_000,
  });
}

export function useHealth(options?: Partial<UseQueryOptions<Health>>) {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.get<Health>("/api/v1/health"),
    ...options,
  });
}

// ---------------------------------------------------------------------
// Zamówienia
// ---------------------------------------------------------------------

const ORDERS_PAGE_SIZE = 20;

export function useOrders(page = 0) {
  return useQuery({
    queryKey: ["orders", page],
    queryFn: () =>
      api.get<Order[]>(
        `/api/v1/orders?limit=${ORDERS_PAGE_SIZE}&offset=${page * ORDERS_PAGE_SIZE}`
      ),
  });
}

export function useOrder(externalId: string | undefined) {
  return useQuery({
    queryKey: ["order", externalId],
    queryFn: () => api.get<Order>(`/api/v1/orders/${encodeURIComponent(externalId!)}`),
    enabled: Boolean(externalId),
  });
}

export function useSearchOrders(query: string) {
  return useQuery({
    queryKey: ["orders-search", query],
    queryFn: () =>
      api.get<Order[]>(`/api/v1/orders/search?q=${encodeURIComponent(query)}`),
    enabled: query.trim().length > 0,
  });
}

/**
 * Status przesyłki jako mutacja (nie query) - pobierany wyłącznie na
 * żądanie użytkownika ("Sprawdź przesyłkę"), nigdy automatycznie w tle,
 * zgodnie z zachowaniem komendy /tracking w bocie.
 */
export function useOrderTracking() {
  return useMutation({
    mutationFn: (externalId: string) =>
      api.get<Shipment>(`/api/v1/orders/${encodeURIComponent(externalId)}/tracking`),
  });
}

export function useTriggerSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<SyncResult>("/api/v1/orders/sync"),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["orders"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

// ---------------------------------------------------------------------
// Magazyn
// ---------------------------------------------------------------------

export function useStock() {
  return useQuery({
    queryKey: ["stock"],
    queryFn: () => api.get<StockItem[]>("/api/v1/stock"),
  });
}

export function useStockItem(sku: string | undefined) {
  return useQuery({
    queryKey: ["stock-item", sku],
    queryFn: () => api.get<StockItem>(`/api/v1/stock/${encodeURIComponent(sku!)}`),
    enabled: Boolean(sku),
  });
}

export function useStockHistory(sku: string | undefined) {
  return useQuery({
    queryKey: ["stock-history", sku],
    queryFn: () =>
      api.get<StockMovement[]>(`/api/v1/stock/${encodeURIComponent(sku!)}/history`),
    enabled: Boolean(sku),
  });
}

export function useStockReport() {
  return useQuery({
    queryKey: ["stock-report"],
    queryFn: () => api.get<StockReport>("/api/v1/stock/report"),
  });
}

/**
 * Oferty sprzedane bez powiązania z magazynem. Ich sprzedaż nie zmienia
 * stanów, więc bez tego ostrzeżenia magazyn po prostu „stoi w miejscu”.
 */
export function useUnmappedOffers() {
  return useQuery({
    queryKey: ["unmapped-offers"],
    queryFn: () => api.get<UnmappedOffer[]>("/api/v1/stock/offers/unmapped"),
  });
}

export interface AdjustStockInput {
  sku: string;
  op: StockAdjustOp;
  quantity: number;
  reason?: string;
}

export function useAdjustStock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sku, ...body }: AdjustStockInput) =>
      api.post<StockItem>(`/api/v1/stock/${encodeURIComponent(sku)}/adjust`, body),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["stock"] });
      void queryClient.invalidateQueries({ queryKey: ["stock-item", variables.sku] });
      void queryClient.invalidateQueries({ queryKey: ["stock-history", variables.sku] });
      void queryClient.invalidateQueries({ queryKey: ["stock-report"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export interface CreateStockItemInput {
  sku: string;
  name: string;
  min_stock?: number;
}

export function useCreateStockItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateStockItemInput) =>
      api.post<StockItem>("/api/v1/stock", body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["stock"] });
    },
  });
}

// ---------------------------------------------------------------------
// Logi
// ---------------------------------------------------------------------

export function useLogs() {
  return useQuery({
    queryKey: ["logs"],
    queryFn: () => api.get<EventLog[]>("/api/v1/logs?limit=50"),
  });
}

// ---------------------------------------------------------------------
// Web Push (PWA)
// ---------------------------------------------------------------------

export function useVapidStatus() {
  return useQuery({
    queryKey: ["vapid-status"],
    queryFn: () => api.get<VapidStatus>("/api/v1/push/vapid-public-key"),
  });
}

export function useSubscribePush() {
  return useMutation({
    mutationFn: (body: PushSubscribeBody) => api.post<void>("/api/v1/push/subscribe", body),
  });
}

export function useUnsubscribePush() {
  return useMutation({
    mutationFn: (endpoint: string) => api.del<void>("/api/v1/push/subscribe", { endpoint }),
  });
}

export function useSendTestPush() {
  return useMutation({
    mutationFn: () => api.post<{ status: string; sent_to: number }>("/api/v1/push/test"),
  });
}

// ---------------------------------------------------------------------
// Zwroty, dyskusje, skrzynka - podgląd tylko do odczytu (bez akcji
// piszących - te żyją wyłącznie w aplikacji desktopowej ORDLY).
// ---------------------------------------------------------------------

export function useReturns() {
  return useQuery({
    queryKey: ["returns"],
    queryFn: () => api.get<ReturnItem[]>("/api/v1/returns"),
  });
}

export function useIssues() {
  return useQuery({
    queryKey: ["issues"],
    queryFn: () => api.get<Issue[]>("/api/v1/issues"),
  });
}

export function useIssueMessages(issueId: string | undefined) {
  return useQuery({
    queryKey: ["issue-messages", issueId],
    queryFn: () =>
      api.get<IssueMessage[]>(`/api/v1/issues/${encodeURIComponent(issueId!)}/messages`),
    enabled: Boolean(issueId),
  });
}

export function useMailMessages(source?: MailSource, unreadOnly = false) {
  return useQuery({
    queryKey: ["mail-messages", source ?? "all", unreadOnly],
    queryFn: () => {
      const params = new URLSearchParams();
      if (source) params.set("source", source);
      if (unreadOnly) params.set("unread_only", "true");
      const qs = params.toString();
      return api.get<MailMessage[]>(`/api/v1/mail/messages${qs ? `?${qs}` : ""}`);
    },
  });
}

/**
 * Pelna tresc jednego maila - zapytanie idzie do backendu dopiero przy
 * otwarciu wiadomosci, bo tam konczy sie polaczeniem z IMAP. Stad
 * `staleTime` na 5 minut: powrot do tej samej wiadomosci nie ma po co
 * meczyc skrzynki drugi raz.
 */
export function useMailBody(messageId: string | undefined) {
  return useQuery({
    queryKey: ["mail-body", messageId],
    queryFn: () =>
      api.get<MailBody>(`/api/v1/mail/messages/${encodeURIComponent(messageId!)}/body`),
    enabled: Boolean(messageId),
    retry: false,
    staleTime: 5 * 60_000,
  });
}

export function useMarkMailRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (messageId: string) =>
      api.post<void>(`/api/v1/mail/messages/${encodeURIComponent(messageId)}/mark-read`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["mail-messages"] });
    },
  });
}
