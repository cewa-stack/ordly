# APPPLANS 05 — Integracja OLX

> Zależności: `appplans_02_sync_engine.md` (architektura pluginowa + sync cycle).

## 1. Ważne zastrzeżenie do przeczytania PRZED implementacją

W przeciwieństwie do Allegro, **OLX nie udostępnia publicznie otwartego, samoobsługowego API
dla sprzedawców** na takich zasadach jak Allegro Developer Portal. OLX ma API partnerskie
("OLX API" / integracje dla dużych sprzedawców), ale zwykle wymaga to:
- podpisania umowy partnerskiej z OLX Group,
- dedykowanego dostępu przyznawanego indywidualnie (nie ma prostej rejestracji "developer
  account" jak w Allegro).

**Pierwszy krok tego modułu to NIE pisanie kodu, tylko weryfikacja dostępu:**
1. Sprawdzić na stronie OLX (dla Polski: olx.pl) czy w danym momencie istnieje program
   partnerski/API dla kont sprzedawcy, do którego można się zarejestrować.
2. Jeśli tak — uzyskać dokumentację API i dopiero wtedy realizować sekcje 2-5 poniżej.
3. Jeśli nie ma dostępnego API — **nie stosować web scrapingu strony OLX** jako obejścia:
   narusza to Regulamin OLX (Terms of Service), grozi zbanowaniem konta i jest kruche
   (layout strony zmienia się bez ostrzeżenia, scraper się psuje). Zamiast tego wdrożyć
   **Wariant B: import/eksport manualny** opisany w sekcji 6.

## 2. Wariant A — jeśli dostęp do OLX API jest dostępny

Struktura analogiczna do pluginu Allegro (architektura pluginowa Comcio):
```
plugins/olx/
  __init__.py
  auth.py       # flow autoryzacji wg dokumentacji OLX (prawdopodobnie OAuth2, do potwierdzenia)
  offers.py     # sync ofert
  orders.py     # sync zamówień/wiadomości (zależnie co API udostępnia)
  models.py     # Pydantic DTOs
```

Plugin musi zaimplementować wspólny interfejs `MarketplacePlugin` (jeśli taki interfejs już
istnieje w Comcio z architektury pluginowej — użyć go; jeśli nie istnieje jeszcze formalnie,
ten moduł jest dobrą okazją żeby go wydzielić z istniejącego kodu Allegro):

```python
class MarketplacePlugin(Protocol):
    name: str
    async def sync(self) -> list[Change]: ...
    async def is_healthy(self) -> bool: ...
```

Podpięcie do `run_sync_cycle` z `appplans_02` — dodać `olx_plugin` do listy
`registered_plugins`, zero zmian w samym schedulerze (to jest sens architektury pluginowej).

## 3. Model danych (Wariant A)

```python
class OlxOffer(Base):
    __tablename__ = "olx_offers"
    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str]
    price: Mapped[float]
    stock: Mapped[int | None]
    status: Mapped[str]
    url: Mapped[str]
    last_synced_at: Mapped[datetime]
```
Migracja przez Alembic.

## 4. UI Desktop (Wariant A)

Nowa sekcja "OLX" w menu bocznym, analogiczna do widoku ofert Allegro:
`src/features/olx/OlxOffersView.tsx` — tabela ofert, status, link do oferty na OLX. Jeśli
OLX API nie udostępnia zamówień/wiadomości (częsty przypadek — wiele integracji OLX kończy
się na samych ogłoszeniach), sekcja ogranicza się do widoku ofert + stanu magazynowego, bez
zakładki "zamówienia OLX".

## 5. Mapowanie magazynu — wspólny stan między Allegro i OLX

Jeśli ten sam produkt (to samo SKU) jest wystawiony i na Allegro, i na OLX, potrzebny jest
mechanizm łączenia stanu magazynowego, żeby sprzedaż na jednym marketplace zmniejszała stan
widoczny na drugim (unikanie oversellingu):

```python
class ProductLink(Base):
    __tablename__ = "product_links"
    sku: Mapped[str] = mapped_column(primary_key=True)
    allegro_offer_id: Mapped[str | None]
    olx_offer_id: Mapped[str | None]
    unified_stock: Mapped[int]
```
Logika: przy sprzedaży wykrytej na dowolnym marketplace, `unified_stock` się zmniejsza, a
sync cycle przy następnym ticku aktualizuje stan na WSZYSTKICH połączonych ofertach (jeśli
OLX API pozwala na update stanu — jeśli nie pozwala, przynajmniej wysłać powiadomienie
"sprzedano na Allegro, zaktualizuj ręcznie ofertę OLX", patrz `appplans_01` dla powiadomień
mobile).

## 6. Wariant B — brak API, import/eksport manualny (fallback)

Jeśli OLX API jest niedostępne, zamiast integracji live:
1. Desktop app dostaje prosty **import CSV/XLSX** — user eksportuje swoje ogłoszenia z panelu
   OLX (jeśli OLX udostępnia taki eksport) lub wpisuje ręcznie, a aplikacja tylko przechowuje
   te dane lokalnie do celów raportowania i łączenia z magazynem (bez auto-sync).
2. Sekcja OLX w UI oznaczona jako "tryb manualny" z przyciskiem `Zaimportuj z pliku` +
   `Edytuj ręcznie`.
3. Ten wariant NIE bierze udziału w automatycznym cyklu sync co 60s — to zwykła sekcja CRUD
   w lokalnej bazie desktopu.

## 7. Testy wymagane

- (Wariant A) Unit: mapowanie DTO z przykładowych odpowiedzi API OLX.
- (Wariant A) Integration: sync cycle wykrywa nową ofertę OLX → event trafia na WebSocket.
- (Oba warianty) Unit: `ProductLink` — sprzedaż na Allegro poprawnie zmniejsza
  `unified_stock` i generuje event dla powiązanej oferty OLX.
- (Wariant B) Unit: parser importu CSV — poprawna obsługa brakujących kolumn, duplikatów SKU.

## 8. Definition of Done

- [ ] Zweryfikowano faktyczną dostępność OLX API w momencie wdrożenia (udokumentowane w
      komentarzu w kodzie + w AGENT.md, z datą sprawdzenia).
- [ ] Wdrożony Wariant A (jeśli API dostępne) LUB Wariant B (jeśli brak) — nie oba naraz.
- [ ] Mechanizm `ProductLink` łączy magazyn między marketplace'ami niezależnie od wariantu.
- [ ] Brak jakiegokolwiek scrapingu strony OLX w kodzie.
