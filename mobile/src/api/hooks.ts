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
  CatalogSync,
  Dashboard,
  EventLog,
  Health,
  Issue,
  IssueMessage,
  MailBody,
  MailMessage,
  MailSource,
  MarketplaceOffer,
  Order,
  OrdlakChatReply,
  OrdlakConversation,
  OrdlakStatus,
  PushSubscribeBody,
  ReturnItem,
  Shipment,
  SyncResult,
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

// Maksimum, jakie przyjmuje `GET /orders`. Przy 20 lista i odznaka na
// zakładce widziały tylko 20 ostatnich zamówień, a stopka mówiła "to
// wszystkie" - starsze niespakowane zamówienie po cichu znikało z widoku.
const ORDERS_PAGE_SIZE = 100;

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

export function useOffers() {
  return useQuery({
    queryKey: ["offers"],
    queryFn: () => api.get<MarketplaceOffer[]>("/api/v1/stock/offers"),
  });
}

/**
 * Pobranie katalogu z marketplace na żądanie ("Synchronizuj").
 *
 * Mutacja, nie query: to jedyny moment, w którym ORDLY odpytuje API
 * marketplace o listę ofert. Automatyczne odświeżanie w tle zjadałoby
 * limit zapytań, a nowa oferta pojawia się wtedy, gdy człowiek ją
 * wystawi - i wtedy sam naciska przycisk.
 */
export function useSyncCatalog() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<CatalogSync>("/api/v1/stock/sync"),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["offers"] });
    },
  });
}

// ---------------------------------------------------------------------
// Logi
// ---------------------------------------------------------------------

export function useLogs() {
  return useQuery({
    queryKey: ["logs"],
    // Bez "Start/Koniec synchronizacji" - powstają co minutę i zasłaniały
    // wszystko inne. Starszy backend ignoruje nieznany parametr.
    queryFn: () => api.get<EventLog[]>("/api/v1/logs?limit=50&include_sync=false"),
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
    // `expired`/`failed` doszły później - starszy backend na Pi ich nie zwraca.
    mutationFn: () =>
      api.post<{ status: string; sent_to: number; expired?: number; failed?: number }>(
        "/api/v1/push/test"
      ),
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

// ---------------------------------------------------------------------
// Ordlak - asystent
// ---------------------------------------------------------------------

/**
 * Stan modułu: czy klucz API jest ustawiony na Pi i na jakim modelu
 * chodzi. Ekran asystenta pyta o to PRZED pokazaniem pola tekstowego,
 * żeby od razu powiedzieć "brak klucza na Pi" zamiast pozwolić napisać
 * pytanie i dopiero wtedy pokazać błąd.
 */
export function useOrdlakStatus() {
  return useQuery({
    queryKey: ["ordlak-status"],
    queryFn: () => api.get<OrdlakStatus>("/api/v1/ordlak/status"),
    staleTime: 5 * 60_000,
    retry: false,
  });
}

/** Zapisane wątki (bez treści), od ostatnio używanego. */
export function useOrdlakConversations() {
  return useQuery({
    queryKey: ["ordlak-conversations"],
    queryFn: () => api.get<OrdlakConversation[]>("/api/v1/ordlak/conversations"),
    retry: false,
  });
}

/** Jeden wątek z pełną historią wiadomości. */
export function useOrdlakConversation(id: number | null) {
  return useQuery({
    queryKey: ["ordlak-conversation", id],
    queryFn: () => api.get<OrdlakConversation>(`/api/v1/ordlak/conversations/${id!}`),
    enabled: id !== null,
    retry: false,
  });
}

/**
 * Zadaje pytanie asystentowi.
 *
 * Backend otwiera własny zakres sesji i zatwierdza OBIE wypowiedzi przed
 * odpowiedzią, więc `conversation_id` z odpowiedzi zawsze wskazuje na
 * wątek, który już jest w bazie - kolejne pytanie w tym wątku nie
 * dostanie 404.
 */
export function useAskOrdlak() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { message: string; conversationId: number | null }) =>
      api.post<OrdlakChatReply>("/api/v1/ordlak/chat", {
        message: input.message,
        conversation_id: input.conversationId,
      }),
    onSuccess: (reply) => {
      void queryClient.invalidateQueries({ queryKey: ["ordlak-conversations"] });
      void queryClient.invalidateQueries({
        queryKey: ["ordlak-conversation", reply.conversation_id],
      });
    },
  });
}
