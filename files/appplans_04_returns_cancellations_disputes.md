# APPPLANS 04 — Zakładka: Zwroty / Anulowane / Dyskusje (Allegro)

> Zależności: `appplans_02_sync_engine.md` (sync cycle + WebSocket hub muszą już działać).

## 1. Cel

Nowa zakładka w desktop app pokazująca trzy sekcje (osobne pod-taby lub filtr w jednym
widoku): **Zwroty**, **Anulowane zamówienia**, **Otwarte dyskusje** — wszystko pobierane z
Allegro przez Comcio, z możliwością odpowiedzi na dyskusję bezpośrednio z aplikacji.

## 2. Wymagane nowe scope'y OAuth2 Allegro

Obecne aktywne scope'y: `allegro:api:sale:offers:read`, `allegro:api:orders:read`,
`allegro:api:profile:read`, `allegro:api:sale:settings:read`.

Trzeba dodać (jako `ALLEGRO_EXTRA_SCOPES`, zgodnie z istniejącym mechanizmem opcjonalnych
scope'ów z `appplans` desktop app):
- `allegro:api:orders:read` (już jest — obejmuje anulowania w ramach zamówień)
- `allegro:api:disputes` — do dyskusji/sporów (weryfikacja dokładnej nazwy w dokumentacji
  Allegro REST API przed implementacją — nazwy scope'ów bywają aktualizowane)
- `allegro:api:returns` — do zwrotów (analogicznie, zweryfikować aktualną nazwę)

**Krok pierwszy przed kodowaniem:** sprawdzić w oficjalnej dokumentacji Allegro REST API
(developer.allegro.pl) dokładne nazwy endpointów i scope'ów dla:
`GET /order/returns`, `GET /order/checkout-forms/{id}/cancellation`, `GET /disputes` — bo te
mogły się zmienić od czasu pisania tego planu. Nie zakładać nazw na pamięć.

## 3. Backend (Comcio) — nowy plugin submodule

Zgodnie z architekturą pluginową, rozszerzyć istniejący plugin `allegro`, NIE tworzyć nowego
pluginu (to nie jest osobny marketplace, to dodatkowe zasoby tego samego API):

```python
# plugins/allegro/returns.py
class AllegroReturnsSync:
    async def fetch_returns(self, since: datetime) -> list[ReturnDTO]:
        resp = await self.client.get("/order/returns", params={"status": "ALL"})
        return [ReturnDTO.from_api(r) for r in resp.json()["returns"]]

# plugins/allegro/disputes.py
class AllegroDisputesSync:
    async def fetch_open_disputes(self) -> list[DisputeDTO]:
        resp = await self.client.get("/disputes", params={"status": "OPENED"})
        return [DisputeDTO.from_api(d) for d in resp.json()["disputes"]]
```

Te dwie klasy podpinają się pod `run_sync_cycle` z `appplans_02` jako kolejne "resource_type"
w tabeli `sync_state` (`"returns"`, `"disputes"`). Anulowania nie wymagają osobnego fetcha —
wykrywane są jako zmiana statusu w istniejącym sync zamówień (`status: CANCELLED`), więc tylko
dodać obsługę tego statusu w istniejącym `orders.py` pluginu, jeśli jeszcze jej nie ma.

## 4. Nowe tabele

```python
class AllegroReturn(Base):
    __tablename__ = "allegro_returns"
    id: Mapped[str] = mapped_column(primary_key=True)  # ID z Allegro
    order_id: Mapped[str]
    status: Mapped[str]
    reason: Mapped[str | None]
    created_at: Mapped[datetime]
    raw_json: Mapped[str]  # pełna odpowiedź, przyda się przy debugowaniu zmian API

class AllegroDispute(Base):
    __tablename__ = "allegro_disputes"
    id: Mapped[str] = mapped_column(primary_key=True)
    order_id: Mapped[str]
    status: Mapped[str]
    last_message_at: Mapped[datetime]
    unread_by_seller: Mapped[bool]
    raw_json: Mapped[str]
```
Dodać migrację Alembic.

## 5. REST endpointy dla desktopu

```
GET  /api/v1/returns?status=&limit=&offset=
GET  /api/v1/disputes?status=open
POST /api/v1/disputes/{id}/reply    body: { "message": str }
GET  /api/v1/orders?status=cancelled
```

`POST /disputes/{id}/reply` — Comcio proxy'uje wysyłkę odpowiedzi do Allegro API
(`POST /disputes/{id}/messages`), NIE robi tego desktop app bezpośrednio (jedyne miejsce
trzymające token Allegro to Comcio po tej refaktoryzacji — patrz uwaga w sekcji 7).

## 6. UI Desktop — nowa zakładka

Struktura komponentu (React + TS):
```
src/features/allegro-issues/
  IssuesTabView.tsx        // kontener z 3 pod-zakładkami
  ReturnsList.tsx
  CancellationsList.tsx
  DisputesList.tsx
  DisputeThread.tsx        // widok konwersacji + pole odpowiedzi
```

- Każda lista: tabela z kolumnami (nr zamówienia, klient, data, status, akcja).
- `DisputeThread`: wątek wiadomości (jak czat), pole tekstowe + przycisk `Wyślij odpowiedź`,
  wywołuje `POST /disputes/{id}/reply` przez `comcioClient`.
- Badge z liczbą nieprzeczytanych dyskusji na ikonie zakładki w menu bocznym (aktualizowany
  przez WebSocket event `dispute_opened` / nowa wiadomość w dyspucie).
- Filtrowanie: dropdown status (Wszystkie / W trakcie / Zamknięte).

## 7. Ważna uwaga architektoniczna — refaktoryzacja tokenu

To jest zmiana ryzykowna, więc zaznaczam osobno: obecnie OAuth2 PKCE i token Allegro są
trzymane w Electron main procesie (`electron/allegroAuth.js`). Zgodnie z decyzją z
`appplans_00` (RPi = jedyne źródło prawdy dla zewnętrznych API), token Allegro powinien
finalnie żyć w Comcio, nie w Electron.

**Podejście rekomendowane (migracja stopniowa, nie "big bang"):**
1. Nowe funkcje (zwroty, dyspaty, dalej OLX, mail) korzystają WYŁĄCZNIE z tokenu po stronie
   Comcio — tam trzeba zaimplementować analogiczny flow OAuth2 PKCE (Python: `authlib` lub
   ręczny PKCE z `httpx`), z tokenami szyfrowanymi Fernetem (mechanizm już istnieje w Comcio).
2. Istniejące funkcje desktopu (oferty, zamówienia) zostają na starym flow do czasu osobnej
   sesji refaktoryzacyjnej — NIE ruszać ich w tym module, żeby nie zwiększać ryzyka regresji.
3. Dodać w AGENT.md desktopu notatkę: "docelowo token Allegro migruje w całości do Comcio,
   patrz appplans_04 sekcja 7" — żeby przyszłe sesje wiedziały o planowanym kierunku.

## 8. Testy wymagane

- Unit: `ReturnDTO.from_api` / `DisputeDTO.from_api` — parsowanie przykładowych payloadów
  Allegro (użyć fixture'ów JSON z prawdziwej struktury odpowiedzi API).
- Integration: sync cycle wykrywa nową dyskusję → event `dispute_opened` trafia na WebSocket.
- UI: wysłanie odpowiedzi w dyspucie → optymistyczne dodanie do wątku + rollback przy błędzie
  sieci.
- Edge case: zwrot bez podanego `reason` (pole opcjonalne) nie wywala UI.

## 9. Definition of Done

- [ ] Nowe scope'y OAuth2 zweryfikowane w aktualnej dokumentacji Allegro (nie zgadywane).
- [ ] Sync zwrotów i dyskusji działa w cyklu 60s, widoczny w logach.
- [ ] Zakładka w UI z 3 sekcjami, badge z licznikiem nieprzeczytanych.
- [ ] Odpowiedź na dyskusję wysyła się realnie do Allegro (test na koncie testowym/sandbox
      jeśli Allegro takowy udostępnia, inaczej ostrożnie na koncie produkcyjnym z niskim
      ryzykiem).
- [ ] Notatka o docelowej migracji tokenu do Comcio dodana do AGENT.md.
