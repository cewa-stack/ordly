# APPPLANS 03 — Przycisk "Napisz maila do hurtowni"

> Zależności: brak (moduł niezależny, można wdrożyć równolegle z `appplans_02`).
> Dotyczy wyłącznie desktop app (Electron).

## 1. Cel

Przycisk w UI (np. na widoku oferty/produktu lub w widoku magazynu przy niskim stanie), który
otwiera formularz z gotowym szablonem maila do hurtowni z prośbą o zakup/dostawę produktów,
i wysyła go przez SMTP.

## 2. Model danych — hurtownie (Wholesalers)

```typescript
// src/types/wholesaler.ts
export interface Wholesaler {
  id: string;
  name: string;
  email: string;
  contactPerson?: string;
  defaultTemplate?: string;   // opcjonalny custom szablon per hurtownia
  linkedProductSkus: string[]; // które SKU zamawiamy u tej hurtowni
}
```

Przechowywanie: lokalna baza SQLite w Electron (np. `better-sqlite3` lub istniejący mechanizm
przechowywania configu aplikacji) — NIE w Comcio, bo to dane czysto desktopowe/prywatne
użytkownika, nie wymagają synchronizacji z telefonem (chyba że użytkownik zdecyduje inaczej —
wtedy patrz sekcja 6 "opcjonalne rozszerzenie").

## 3. UI — komponent

1. Widok "Magazyn" / "Produkt": przy każdym produkcie przycisk `Zamów u hurtowni` (widoczny
   zawsze, ale wyróżniony kolorem gdy stan < próg alertu).
2. Kliknięcie otwiera modal `WholesalerEmailModal`:
   - Dropdown wyboru hurtowni (filtrowany po `linkedProductSkus`, z opcją "inna hurtownia").
   - Lista produktów do zamówienia (pre-wypełniona produktem, z możliwością dodania kolejnych
     z tej samej hurtowni) + pole ilości per produkt.
   - Pole treści maila — pre-wypełnione szablonem, w pełni edytowalne przed wysyłką.
   - Przycisk `Wyślij` + `Podgląd` (żeby zobaczyć finalny render przed wysłaniem).

## 4. Szablon domyślny

```typescript
function buildDefaultEmailBody(wholesaler: Wholesaler, items: OrderItem[]): string {
  const itemsList = items
    .map(i => `- ${i.name} (SKU: ${i.sku}) — ilość: ${i.quantity} szt.`)
    .join('\n');
  return `Dzień dobry${wholesaler.contactPerson ? ` ${wholesaler.contactPerson}` : ''},

Chciałbym złożyć zamówienie na następujące produkty:

${itemsList}

Proszę o potwierdzenie dostępności i przewidywanego terminu dostawy.

Pozdrawiam,
[Twoje dane z ustawień aplikacji]`;
}
```
Dane nadawcy (imię, firma, telefon) pobierane z sekcji Ustawienia aplikacji — dodać tam pola
jeśli jeszcze nie istnieją.

## 5. Wysyłka — backend w Electron main procesie

**Decyzja:** wysyłka SMTP dzieje się w main procesie (nigdy w rendererze) — analogicznie do
wzorca `allegroAuth.js`. Powód: dane logowania SMTP (hasło) nie mogą trafić do kodu renderera
ani do bundla JS widocznego w DevTools.

```javascript
// electron/mailSender.js
const nodemailer = require('nodemailer');

async function sendWholesalerEmail({ to, subject, body }) {
  const transporter = nodemailer.createTransport({
    host: process.env.SMTP_HOST,
    port: Number(process.env.SMTP_PORT || 587),
    secure: process.env.SMTP_PORT === '465',
    auth: { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS },
  });
  return transporter.sendMail({
    from: process.env.SMTP_USER,
    to,
    subject,
    text: body,
  });
}

ipcMain.handle('wholesaler:sendEmail', async (_event, payload) => {
  try {
    const info = await sendWholesalerEmail(payload);
    return { success: true, messageId: info.messageId };
  } catch (err) {
    return { success: false, error: err.message };
  }
});
```

`contextBridge` w `preload.js`:
```javascript
contextBridge.exposeInMainWorld('wholesalerApi', {
  sendEmail: (payload) => ipcRenderer.invoke('wholesaler:sendEmail', payload),
});
```

**Konfiguracja SMTP** — dodać do `.env` (root projektu, bez `VITE_` prefixu, zgodnie z istniejącą
konwencją): `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`. Dla Gmail/Outlook wymagane hasło
aplikacji (app password), nie zwykłe hasło konta — dodać o tym notatkę w README/ustawieniach UI.

## 6. Obsługa błędów i UX

- Walidacja: adres email hurtowni musi przejść przez regex + sprawdzenie że pole treści nie
  jest puste, zanim przycisk `Wyślij` stanie się aktywny.
- Po wysyłce: zapis do lokalnej historii "Wysłane zamówienia do hurtowni" (data, hurtownia,
  lista produktów) — osobna zakładka lub sekcja w widoku hurtowni, żeby user widział historię
  zamówień.
- Błąd SMTP (zły login/hasło, timeout): toast z czytelnym komunikatem + link do sekcji
  Ustawienia > SMTP, nie techniczny stack trace.
- Retry: NIE retry'ować automatycznie wysyłki maila (ryzyko podwójnego zamówienia) — w razie
  błędu user musi świadomie kliknąć `Wyślij ponownie`.

## 7. Opcjonalne rozszerzenie (niska priorytetowo, do rozważenia później)

Jeśli w przyszłości user zechce widzieć historię zamówień do hurtowni też na telefonie —
przenieść tabelę `wholesaler_orders` do Comcio i synchronizować przez REST z modułu 02.
Nie wdrażać teraz, tylko zostawić komentarz w kodzie `// TODO: appplans_03 ext — sync to RPi
if needed`.

## 8. Testy wymagane

- Unit: `buildDefaultEmailBody` — poprawny format dla 1 i wielu produktów, poprawna obsługa
  braku `contactPerson`.
- Unit: walidacja formularza — pusty email hurtowni blokuje wysyłkę.
- Integration (manualna, bo SMTP): wysłać testowego maila na własny adres, zweryfikować
  treść i temat.
- Test błędu: złe dane SMTP w `.env` → aplikacja pokazuje czytelny błąd, nie crashuje.

## 9. Definition of Done

- [ ] Przycisk widoczny na widoku produktu/magazynu, wyróżniony przy niskim stanie.
- [ ] Modal z edytowalnym szablonem, podglądem i wysyłką działa end-to-end.
- [ ] SMTP configurowalny przez `.env`, opisany w README jak skonfigurować app password.
- [ ] Historia wysłanych zamówień widoczna w UI.
- [ ] Zero danych logowania SMTP w kodzie renderera / bundlu JS (weryfikacja: `grep SMTP_PASS`
      w zbudowanym `dist/` nie zwraca wyników).
