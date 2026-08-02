/**
 * Service worker ORDLY Mobile (PWA) - wyłącznie do Web Push.
 *
 * Celowo NIE cache'uje zasobów aplikacji (żadnego "offline app shell") -
 * to osobny problem (patrz 01_app.md, Faza 3 "tryb offline"), nierozwiązany
 * jeszcze przez ten plik. Jedyna odpowiedzialność: pokazać powiadomienie
 * push i otworzyć/wskoczyć do aplikacji po kliknięciu.
 */

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let title = "ORDLY";
  let body = "";

  if (event.data) {
    try {
      const payload = event.data.json();
      title = payload.title || title;
      body = payload.body || "";
    } catch (err) {
      body = event.data.text();
    }
  }

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: "/icon.png",
      badge: "/icon.png",
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clientList) => {
        for (const client of clientList) {
          if ("focus" in client) {
            return client.focus();
          }
        }
        if (self.clients.openWindow) {
          return self.clients.openWindow("/");
        }
      })
  );
});
