# APPPLANS 01 — Aplikacja mobilna (powiadomienia + podgląd magazynu)

> Zależności: `appplans_02_sync_engine.md` i `appplans_04_returns_cancellations_disputes.md`
> muszą być wdrożone jako pierwsze — mobile app jest czystym konsumentem ich API.
> Wdrażać jako OSTATNI moduł.

## 1. Zakres (celowo minimalny)

Zgodnie z wymaganiem — telefon to NIE pełna aplikacja zarządzająca, tylko:
1. Push/lokalne powiadomienia o wszystkich eventach (nowe zamówienie, niski stan magazynowy,
   zwrot, dyskusja, nowy mail).
2. Prosty dashboard: lista produktów ze stanem magazynowym (read-only, bez edycji z telefonu).

Świadomie NIE wdrażać na telefonie: edycji ofert, wysyłki maili do hurtowni, odpowiadania na
dyskusje — to zostaje na desktopie, zgodnie z podziałem z wymagań użytkownika.

## 2. Wybór technologii

**Rekomendacja: Expo (React Native) + TypeScript.** Powód: reużycie wiedzy TS z projektu
desktopowego, Expo znacząco upraszcza konfigurację push notifications (Expo Push Service)
i buduje na iOS bez potrzeby pełnego Xcode setupu do developmentu (potrzebny tylko do
finalnego publish/TestFlight).

Alternatywa rozważona i odrzucona: PWA (Progressive Web App) — odrzucona, bo push
notifications na iOS Safari mają istotne ograniczenia (do niedawna w ogóle niedostępne,
nadal mniej niezawodne niż natywny push). Dla realnych, pilnych alertów o magazynie to
nieakceptowalne ryzyko przegapienia powiadomienia.

## 3. Struktura projektu

```
mobile/
  App.tsx
  src/
    services/
      comcioClient.ts     // REST + WebSocket klient, analogiczny kontrakt do desktopu
      pushRegistration.ts // rejestracja tokenu Expo Push w Comcio
      pairing.ts          // skan QR + zapis JWT w expo-secure-store
    screens/
      PairingScreen.tsx
      DashboardScreen.tsx   // lista produktów + stan magazynowy
      NotificationsScreen.tsx // historia powiadomień
      SettingsScreen.tsx
    types/
      events.ts            // te same typy eventów co w appplans_02 (kontrakt współdzielony)
```

## 4. Parowanie z Comcio

Zgodnie z `appplans_02` sekcja 7 — mobile app skanuje QR wyświetlony przez Comcio (endpoint
`GET /pair/qr`), otrzymuje JWT, zapisuje go w `expo-secure-store`. Ekran `PairingScreen`
używa `expo-camera` do skanu.

**Wymagane od użytkownika przed tym krokiem**: telefon i Raspberry Pi muszą być w tej samej
sieci lokalnej (Wi-Fi domowe) w momencie parowania, chyba że RPi ma wystawiony publiczny
adres (np. przez Tailscale/VPN — rekomendowane rozwiązanie dla dostępu spoza domu, patrz
sekcja 8).

## 5. Rejestracja Push Notifications

```typescript
// src/services/pushRegistration.ts
import * as Notifications from 'expo-notifications';

export async function registerForPush(comcioBaseUrl: string, jwt: string) {
  const { status } = await Notifications.requestPermissionsAsync();
  if (status !== 'granted') return;
  const token = (await Notifications.getExpoPushTokenAsync()).data;
  await fetch(`${comcioBaseUrl}/api/v1/devices/register-push`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${jwt}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ expo_push_token: token }),
  });
}
```

Backend (Comcio) — nowa tabela + endpoint:
```python
class DevicePushToken(Base):
    __tablename__ = "device_push_tokens"
    device_id: Mapped[str] = mapped_column(primary_key=True)
    expo_push_token: Mapped[str]
    registered_at: Mapped[datetime]

@router.post("/devices/register-push")
async def register_push(payload: RegisterPushRequest, device=Depends(verify_device_token)):
    await upsert_push_token(device.id, payload.expo_push_token)
```

Wysyłka pusha przy evencie (rozszerzenie `event_bus.publish` z `appplans_02`):
```python
async def publish(self, event: dict):
    await self._broadcast_websocket(event)
    if event["type"] in PUSH_WORTHY_EVENTS:  # nie każdy event = push, np. "sync_error" ciche
        await send_expo_push_batch(event)
```
Użyć `exponent-server-sdk` (Python) do wysyłki batchowej do Expo Push Service.

## 6. Dashboard — podgląd magazynu

```
GET /api/v1/inventory/summary
```
Zwraca listę produktów z: nazwą, SKU, stanem, statusem (OK / niski stan / brak). Ekran
`DashboardScreen` renderuje listę z pull-to-refresh + auto-refresh po evencie
`stock_changed` odebranym przez WebSocket (mobile też utrzymuje WS connection gdy appka jest
w foreground; w tle poleganie wyłącznie na push).

Sortowanie: produkty z niskim/zerowym stanem na górze listy (priorytet uwagi użytkownika).

## 7. Ekran powiadomień (historia)

```
GET /api/v1/notifications?limit=50&offset=
POST /api/v1/notifications/{id}/mark-read
```
Lista czatowa/timeline stylu "co się wydarzyło", z ikonami per typ eventu (nowe zamówienie,
zwrot, dyskusja, mail, niski stan). Tapnięcie w powiadomienie o dyskusji/zwrocie NIE otwiera
edycji (zgodnie z zakresem z pkt 1) — pokazuje tylko szczegóły read-only + komunikat
"Odpowiedz na komputerze w aplikacji Cewastack".

## 8. Dostęp spoza sieci domowej (ważna decyzja do podjęcia z użytkownikiem)

Domyślnie Comcio nasłuchuje tylko w sieci lokalnej. Push notifications działają zawsze
(Expo Push Service jest publiczny), ale REST/WebSocket (dashboard, historia) wymagają
połączenia z RPi. Dwie opcje:
1. **Tailscale** (rekomendowane) — RPi i telefon w tej samej sieci VPN mesh, zero
   przekierowań portów na routerze, szyfrowane end-to-end. Instalacja: `curl -fsSL
   https://tailscale.com/install.sh | sh` na RPi + apka Tailscale na telefonie.
2. Port forwarding na routerze — odradzane, wystawia RPi bezpośrednio do internetu, wyższe
   ryzyko bezpieczeństwa nawet z JWT auth.

Zdecydować z użytkownikiem PRZED wdrożeniem tego kroku — wybór wpływa na `comcioBaseUrl`
w konfiguracji mobile app.

## 9. Testy wymagane

- Unit: `registerForPush` — poprawne wywołanie API przy nadanych uprawnieniach, brak
  wywołania gdy `status !== 'granted'`.
- Integration: event `stock_changed` z severity "critical" → push dociera na testowe
  urządzenie (test manualny z Expo Push Tool).
- UI: `DashboardScreen` — sortowanie produktów niski-stan-first, pull-to-refresh działa.
- Test parowania: nieprawidłowy/wygasły QR → czytelny komunikat błędu, nie crash.

## 10. Definition of Done

- [ ] Parowanie przez QR działa, JWT zapisany bezpiecznie w `expo-secure-store`.
- [ ] Push notifications dochodzą na iOS dla eventów oznaczonych jako `PUSH_WORTHY_EVENTS`.
- [ ] Dashboard pokazuje aktualny stan magazynowy, sortowany wg priorytetu.
- [ ] Historia powiadomień z oznaczaniem jako przeczytane.
- [ ] Decyzja o dostępie zdalnym (Tailscale vs inne) podjęta i udokumentowana w README mobile.
- [ ] Appka nie pozwala na żadną akcję edycyjną (zgodnie z zamierzonym ograniczonym zakresem).
