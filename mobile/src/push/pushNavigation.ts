/**
 * Wejście z powiadomienia w konkretny rekord (sekcja 9.2 pkt 3 spec UI
 * + zasada "Pokaż" z sekcji 04 koncepcji push).
 *
 * Service worker nie może sam nawigować po Reactcie - wysyła więc
 * `postMessage({type:"ordly:navigate", url})`, a ten moduł tłumaczy
 * ścieżkę z powiadomienia na ekran nawigacji.
 *
 * Ścieżki są tym samym słownikiem, którym posługuje się backend przy
 * budowaniu payloadu (`push_payload.py`) - gdy dojdzie nowy typ
 * powiadomienia, trzeba dopisać go W OBU miejscach, inaczej kliknięcie
 * wyląduje na liście zamiast na rekordzie.
 */
import { Platform } from "react-native";

import type { RootStackParamList } from "@/navigation/types";

export type PushTarget =
  | { screen: "OrderDetail"; params: RootStackParamList["OrderDetail"] }
  | { screen: "StockItem"; params: RootStackParamList["StockItem"] }
  | { screen: "IssueDetail"; params: RootStackParamList["IssueDetail"] }
  | { screen: "MailDetail"; params: RootStackParamList["MailDetail"] }
  | { screen: "Settings"; params: undefined }
  | { screen: "MainTab"; params: { tab: "Orders" | "Stock" | "Discussions" | "Mailbox" | "Returns" } };

/**
 * Zamienia ścieżkę z powiadomienia na cel nawigacji.
 *
 * Zwraca `null` dla ścieżek, których nie znamy - lepiej zostawić
 * użytkownika tam, gdzie był, niż rzucić go na losowy ekran.
 */
export function resolvePushTarget(url: string): PushTarget | null {
  const path = url.split("?")[0].replace(/\/+$/, "");
  // Identyfikatory w ścieżce są zakodowane po stronie backendu
  // (`push_payload.py`), bo Message-ID maila zawiera `<`, `>` i `@`.
  // Bez odkodowania ekran szczegółów szukałby wiadomości o adresie
  // `%3Cabc%40...%3E` i nie znalazłby jej nigdy.
  const segments = path.split("/").filter(Boolean).map(safeDecode);

  if (segments.length === 0) return null;

  const [head, id] = segments;

  if (head === "orders") {
    return id
      ? { screen: "OrderDetail", params: { externalId: id } }
      : { screen: "MainTab", params: { tab: "Orders" } };
  }
  if (head === "stock") {
    return id
      ? { screen: "StockItem", params: { sku: id } }
      : { screen: "MainTab", params: { tab: "Stock" } };
  }
  if (head === "issues") {
    return id
      ? { screen: "IssueDetail", params: { issueId: id } }
      : { screen: "MainTab", params: { tab: "Discussions" } };
  }
  if (head === "mailbox") {
    return id
      ? { screen: "MailDetail", params: { messageId: id } }
      : { screen: "MainTab", params: { tab: "Mailbox" } };
  }
  if (head === "returns") {
    // Zwroty są wyłącznie listą - koncepcja mobilna nie ma ekranu
    // szczegółów zwrotu, bo decyzję i tak podejmuje się na desktopie.
    return { screen: "MainTab", params: { tab: "Returns" } };
  }
  if (head === "settings") {
    return { screen: "Settings", params: undefined };
  }

  return null;
}

/** Uszkodzone kodowanie procentowe nie może wywrócić nawigacji z powiadomienia. */
function safeDecode(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

type NavigateHandler = (target: PushTarget) => void;

/**
 * Podpina nasłuch wiadomości z service workera.
 *
 * Zwraca funkcję odpinającą. Poza kompilacją web nie robi nic - natywne
 * buildy dostaną docelowo Expo Push, który ma własny mechanizm wejścia
 * z powiadomienia.
 */
export function subscribeToPushNavigation(onNavigate: NavigateHandler): () => void {
  if (Platform.OS !== "web" || typeof navigator === "undefined") {
    return () => undefined;
  }
  if (!("serviceWorker" in navigator)) {
    return () => undefined;
  }

  function handleMessage(event: MessageEvent) {
    const data = event.data as { type?: string; url?: string } | null;
    if (!data || data.type !== "ordly:navigate" || !data.url) return;

    const target = resolvePushTarget(data.url);
    if (target) onNavigate(target);
  }

  navigator.serviceWorker.addEventListener("message", handleMessage);
  return () => navigator.serviceWorker.removeEventListener("message", handleMessage);
}

/**
 * Ścieżka, z którą aplikacja została OTWARTA z powiadomienia (zimny
 * start - okna jeszcze nie było, więc service worker zrobił
 * `openWindow(url)` zamiast `postMessage`).
 */
export function consumeInitialPushTarget(): PushTarget | null {
  if (Platform.OS !== "web" || typeof window === "undefined") return null;

  const target = resolvePushTarget(window.location.pathname);
  if (target && window.history?.replaceState) {
    // Czyścimy adres, żeby odświeżenie strony nie wrzucało użytkownika
    // znowu w ten sam rekord.
    window.history.replaceState({}, "", "/");
  }
  return target;
}
