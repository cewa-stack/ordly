/**
 * Service worker ORDLY Mobile (PWA) - wyłącznie do Web Push.
 *
 * Celowo NIE cache'uje zasobów aplikacji (żadnego "offline app shell") -
 * to osobny problem (patrz 01_app.md, Faza 3 "tryb offline"), nierozwiązany
 * jeszcze przez ten plik.
 *
 * Odpowiedzialności:
 * 1. pokazać powiadomienie z katalogu (tytuł, treść, grupowanie, akcje),
 * 2. otworzyć KONKRETNY rekord po kliknięciu, nie samą aplikację,
 * 3. obsłużyć "Wycisz na godzinę" bez wchodzenia do aplikacji,
 * 4. utrzymać plakietkę z liczbą spraw do decyzji.
 *
 * Zasada nadrzędna (sekcja 04 koncepcji push): żadna akcja z
 * powiadomienia nie zmienia danych. Telefon pokazuje, desktop robi.
 */

const MUTE_DURATION_MS = 60 * 60 * 1000;
const MUTE_STORAGE_KEY = "ordly-muted-until";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

/**
 * Wyciszenie trzymane jest w Cache API, bo service worker nie ma dostępu
 * do localStorage, a IndexedDB do przechowania jednej liczby to armata
 * na muchę. Klucz jest sztucznym URL-em - Cache API indeksuje po żądaniach.
 */
async function readMutedUntil() {
  try {
    const cache = await caches.open("ordly-state");
    const response = await cache.match(MUTE_STORAGE_KEY);
    if (!response) return 0;
    const value = await response.text();
    return Number(value) || 0;
  } catch (err) {
    return 0;
  }
}

async function writeMutedUntil(timestamp) {
  const cache = await caches.open("ordly-state");
  await cache.put(MUTE_STORAGE_KEY, new Response(String(timestamp)));
}

/**
 * Plakietka liczy WYŁĄCZNIE sprawy wymagające decyzji na desktopie
 * (zamówienia do spakowania, pytania bez odpowiedzi, zwroty) - liczbę
 * podaje backend w payloadzie. `null` znaczy "nie ruszaj plakietki",
 * np. przy cichym potwierdzeniu z hurtowni.
 */
async function applyBadge(count) {
  if (count === null || count === undefined) return;
  try {
    if (count > 0 && self.navigator.setAppBadge) {
      await self.navigator.setAppBadge(count);
    } else if (self.navigator.clearAppBadge) {
      await self.navigator.clearAppBadge();
    }
  } catch (err) {
    // Badging API nie jest wspierane wszędzie (m.in. starsze Safari) -
    // brak plakietki nie może przerwać pokazania powiadomienia.
  }
}

self.addEventListener("push", (event) => {
  event.waitUntil(handlePush(event));
});

async function handlePush(event) {
  let payload = { title: "ORDLY", body: "" };

  if (event.data) {
    try {
      payload = event.data.json();
    } catch (err) {
      payload = { title: "ORDLY", body: event.data.text() };
    }
  }

  const mutedUntil = await readMutedUntil();
  const isMuted = Date.now() < mutedUntil;

  await applyBadge(payload.badge);

  await self.registration.showNotification(payload.title || "ORDLY", {
    body: payload.body || "",
    icon: "/icon.png",
    badge: "/icon.png",
    // `tag` ZASTĘPUJE powiadomienie o tym samym kluczu. Backend dobiera
    // go świadomie: zbiorcze zamówienia mają wspólny klucz (nowsze
    // zastępuje starsze), pojedyncze rekordy - własny (leżą obok siebie).
    tag: payload.tag || "ordly",
    // Bez tego przeglądarka podmienia treść po cichu, gdy tag się
    // powtarza - użytkownik nie zauważyłby, że "3 nowe" zmieniło się
    // w "4 nowe".
    renotify: true,
    silent: Boolean(payload.silent) || isMuted,
    requireInteraction: false,
    data: {
      url: payload.url || "/",
      thread: payload.thread || "orders",
    },
    actions: (payload.actions || []).slice(0, 2),
  });
}

self.addEventListener("notificationclick", (event) => {
  const notification = event.notification;
  notification.close();

  if (event.action === "mute") {
    event.waitUntil(writeMutedUntil(Date.now() + MUTE_DURATION_MS));
    return;
  }

  const targetUrl = (notification.data && notification.data.url) || "/";
  event.waitUntil(openTarget(targetUrl));
});

/**
 * Otwiera konkretny rekord. Gdy aplikacja już działa, nie przeładowuje
 * jej - wysyła wiadomość do okna i tylko podnosi je na wierzch, żeby
 * nawigacja odbyła się w Reakcie, bez utraty stanu i sesji.
 */
async function openTarget(targetUrl) {
  const clientList = await self.clients.matchAll({
    type: "window",
    includeUncontrolled: true,
  });

  for (const client of clientList) {
    if ("focus" in client) {
      client.postMessage({ type: "ordly:navigate", url: targetUrl });
      return client.focus();
    }
  }

  if (self.clients.openWindow) {
    return self.clients.openWindow(targetUrl);
  }
}
