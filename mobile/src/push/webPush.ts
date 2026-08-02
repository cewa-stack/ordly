/**
 * Web Push (RFC 8030) - działa WYŁĄCZNIE w kompilacji web (`Platform.OS
 * === "web"`), czyli gdy ORDLY Mobile jest otwarty jako PWA w Safari/Chrome.
 * Natywne kompilacje (iOS/Android) mają dostać docelowo powiadomienia
 * przez Expo Push (Faza 2, 01_app.md) - to nie jest ten sam mechanizm.
 *
 * Dlaczego to osobny plik, nie hook: rejestracja service workera i
 * wstrzyknięcie <link rel="manifest"> to efekty uboczne na `document`,
 * które mają się wykonać raz przy starcie apki (App.tsx), niezależnie od
 * cyklu życia komponentów ekranu Ustawienia.
 */
import { Platform } from "react-native";

export function isWebPushSupported(): boolean {
  return (
    Platform.OS === "web" &&
    typeof navigator !== "undefined" &&
    "serviceWorker" in navigator &&
    typeof window !== "undefined" &&
    "PushManager" in window
  );
}

/**
 * Wstrzykuje manifest PWA i meta-tagi wymagane przez iOS Safari, żeby
 * "Dodaj do ekranu początkowego" otwierało apkę w trybie standalone
 * (bez paska adresu) zamiast zwykłej karty przeglądarki. Safari **ignoruje**
 * `display: standalone` z manifest.json i wymaga tych starszych,
 * webkit-owych meta-tagów - stąd dublowanie z manifest.json.
 */
export function injectPwaHeadTags(): void {
  if (Platform.OS !== "web" || typeof document === "undefined") {
    return;
  }

  if (!document.querySelector('link[rel="manifest"]')) {
    const manifestLink = document.createElement("link");
    manifestLink.rel = "manifest";
    manifestLink.href = "/manifest.json";
    document.head.appendChild(manifestLink);
  }

  const metaTags: Array<[string, string]> = [
    ["apple-mobile-web-app-capable", "yes"],
    ["apple-mobile-web-app-status-bar-style", "black-translucent"],
    ["apple-mobile-web-app-title", "ORDLY"],
    ["theme-color", "#0D1117"],
  ];
  for (const [name, content] of metaTags) {
    if (!document.querySelector(`meta[name="${name}"]`)) {
      const meta = document.createElement("meta");
      meta.name = name;
      meta.content = content;
      document.head.appendChild(meta);
    }
  }

  if (!document.querySelector('link[rel="apple-touch-icon"]')) {
    const touchIcon = document.createElement("link");
    touchIcon.rel = "apple-touch-icon";
    touchIcon.href = "/icon.png";
    document.head.appendChild(touchIcon);
  }
}

export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (!isWebPushSupported()) {
    return null;
  }
  return navigator.serviceWorker.register("/sw.js");
}

function urlBase64ToUint8Array(base64Url: string): Uint8Array {
  const padding = "=".repeat((4 - (base64Url.length % 4)) % 4);
  const base64 = (base64Url + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const output = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i += 1) {
    output[i] = rawData.charCodeAt(i);
  }
  return output;
}

export async function getExistingPushSubscription(): Promise<PushSubscription | null> {
  if (!isWebPushSupported()) {
    return null;
  }
  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.getSubscription();
}

export async function subscribeToPush(vapidPublicKey: string): Promise<PushSubscription> {
  if (!isWebPushSupported()) {
    throw new Error("Ta przeglądarka nie obsługuje powiadomień push.");
  }

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Brak zgody na powiadomienia - włącz je w ustawieniach przeglądarki.");
  }

  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
  });
}

export async function unsubscribeFromPush(): Promise<string | null> {
  const subscription = await getExistingPushSubscription();
  if (!subscription) {
    return null;
  }
  const endpoint = subscription.endpoint;
  await subscription.unsubscribe();
  return endpoint;
}
