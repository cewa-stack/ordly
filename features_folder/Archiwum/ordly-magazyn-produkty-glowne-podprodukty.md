# ORDLY — Produkty główne i podprodukty (stan magazynowy w parze)

## Kontekst i decyzja architektoniczna

Dotychczasowy mechanizm `offer_links` (oferta marketplace → N niezależnych
składników magazynowych z ilością każdego) **zostaje**, bo nadal jest
potrzebny do mapowania oferty na magazyn i do prawdziwych zestawów
(np. jedna oferta łącząca dwa niezwiązane ze sobą produkty główne).

Dochodzi do niego **nowa, osobna relacja na poziomie samego magazynu**:
produkt może mieć **produkt główny** (parent) — wtedy jego stan zawsze
porusza się w parze ze stanem produktu głównego, niezależnie od tego,
przez którą ofertę/marketplace nastąpiła sprzedaż.

Przykład z życia: **Butelka 10ml** to produkt główny. **Nakrętka 10ml**
i **Kroplomierz 10ml** to jej podprodukty (1:1). W magazynie widoczna
jest tylko „Butelka 10ml” (z możliwością rozwinięcia i podejrzenia
podproduktów) — nakrętka i kroplomierz nie zaśmiecają głównej listy.
Gdy cokolwiek sprzeda się jako „Butelka 10ml” (przez `offer_links` albo
dopasowanie po SKU), po odjęciu stanu butelki system **automatycznie**
odejmuje dokładnie tyle samo sztuk z nakrętki i kroplomierza.

### Ustalone z użytkownikiem zasady (nie negocjuj, nie zmieniaj)
1. **Proporcja zawsze 1:1** — bez konfigurowalnych mnożników per podprodukt.
   Nie buduj pola „ilość na 1 sztukę produktu głównego” — nie jest potrzebne.
2. **Zagnieżdżenie tylko sprzedażowe** — kaskada działa WYŁĄCZNIE dla zmian
   pochodzących ze sprzedaży/anulowania/zwrotu (czyli przez `StockSyncService`).
   Ręczna korekta stanu produktu głównego (`/stock add|remove|set`,
   `POST /stock/{sku}/adjust`, panel „Magazyn” → edycja ręczna) **NIE**
   rusza podproduktów. To świadoma decyzja — inwentaryzacje/dostawy
   liczy się i wpisuje osobno dla każdego SKU.
3. **Zagnieżdżenie jednopoziomowe** — produkt, który sam ma podprodukty,
   nie może zostać niczyim podproduktem, i odwrotnie. Walidacja musi to
   twardo egzekwować.

## 1. Model danych

### Migracja Alembic
Dodaj nullable kolumnę do `inventory_items`:

```python
op.add_column(
    "inventory_items",
    sa.Column("parent_item_id", sa.Integer, sa.ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True),
)
op.create_index("ix_inventory_items_parent_item_id", "inventory_items", ["parent_item_id"])
```

`ondelete="SET NULL"` celowo — usunięcie produktu głównego nie kasuje
kaskadowo podproduktów, tylko odwiązuje je (stają się zwykłymi,
samodzielnymi produktami).

### `InventoryItemModel` (`backend/src/app/database/models/inventory_item_model.py`)
Dodaj:
```python
parent_item_id: Mapped[int | None] = mapped_column(
    ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True, index=True
)
sub_items: Mapped[list["InventoryItemModel"]] = relationship(
    back_populates="parent", remote_side="InventoryItemModel.id",  # popraw kierunek wg SQLAlchemy self-referencing
)
```
(Skonfiguruj self-referencing relationship poprawnie wg dokumentacji
SQLAlchemy 2.0 — `parent` + `sub_items` jako para `remote_side`/`back_populates`.)

### `InventoryItem` (encja domenowa, `domain/entities/inventory_item.py`)
Dodaj pole:
```python
parent_sku: str | None = None
```
(Encja operuje na SKU, nie na ID — spójnie z resztą kodu, który zawsze
adresuje produkty po `sku`, nigdy po ID bazodanowym.)

## 2. Warstwa repozytorium

### `InventoryRepository` (interfejs, `domain/interfaces/inventory_repository.py`)
Dodaj metody abstrakcyjne:
```python
async def get_sub_items(self, parent_sku: str) -> list[InventoryItem]:
    """Zwraca podprodukty przypisane do danego produktu głównego."""

async def set_parent(self, sku: str, parent_sku: str | None) -> None:
    """
    Ustawia lub czyści produkt główny dla danego SKU.

    Raises:
        InventoryItemNotFoundError: gdy sku lub parent_sku nie istnieje.
    """
```

### `SqliteInventoryRepository` (`repositories/sqlite_inventory_repository.py`)
- `get_sub_items`: `SELECT ... WHERE parent_item_id = (SELECT id FROM inventory_items WHERE sku = :parent_sku)`,
  zmapowane na `InventoryItem` z `parent_sku` ustawionym na `parent_sku`.
- `set_parent`: znajdź `item` po `sku`, znajdź `parent` po `parent_sku` (jeśli nie None),
  ustaw `item.parent_item_id = parent.id if parent else None`.
- `get_all()` i `get_by_sku()` — zmapuj też `parent_sku` (join albo osobne query po `parent_item_id` → `sku` rodzica).

## 3. Warstwa serwisowa

### `InventoryService` (`services/inventory_service.py`)
Nowe metody:

```python
async def set_parent(self, sku: str, parent_sku: str | None) -> InventoryItem:
    """
    Ustawia produkt główny dla podanego SKU (albo czyści, gdy parent_sku=None).

    Reguły (patrz sekcja "Ustalone zasady" w spec):
    - sku != parent_sku
    - produkt docelowo-główny (parent_sku) nie może sam mieć produktu głównego
      -> ValueError("Produkt X sam jest podproduktem — zagnieżdżenie tylko jednopoziomowe")
    - sku (ten, który ma zostać podproduktem) nie może już mieć własnych
      podproduktów -> ValueError("Produkt ma własne podprodukty i nie może
      jednocześnie być podproduktem")
    """

async def get_sub_items(self, sku: str) -> list[InventoryItem]:
    """Zwraca podprodukty danego produktu głównego (pusta lista, gdy brak)."""
```

Zaimplementuj walidacje w serwisie (nie w repozytorium) — repozytorium ma
być głupie, logika biznesowa żyje tu, zgodnie z resztą kodu.

### Nowy moduł: `services/sub_item_cascade.py`
```python
"""
Kaskadowanie zmian stanu na podprodukty (1:1, tylko dla zdarzeń sprzedażowych).

Wywoływane WYŁĄCZNIE przez StockSyncService (sprzedaż/anulowanie/zwrot).
Ręczne korekty w InventoryService nigdy tego nie wywołują - patrz spec
"Produkty główne i podprodukty" p.2 (decyzja świadoma, nie bug).
"""
from __future__ import annotations

from app.domain.entities.inventory_item import InventoryItem
from app.domain.interfaces.inventory_repository import InventoryRepository
from app.services.stock_ledger import apply_stock_change


async def cascade_to_sub_items(
    inventory: InventoryRepository,
    parent_sku: str,
    change: int,
    reason: str,
    source: str,
    reference: str,
) -> list[InventoryItem]:
    """
    Aplikuje dokładnie tę samą zmianę (1:1) do wszystkich podproduktów
    danego produktu głównego. Zwraca listę zaktualizowanych podproduktów
    (do sprawdzenia progu niskiego stanu przez wywołującego).
    """
    sub_items = await inventory.get_sub_items(parent_sku)
    updated: list[InventoryItem] = []
    for sub in sub_items:
        result = await apply_stock_change(
            inventory=inventory,
            sku=sub.sku,
            change=change,
            reason=f"{reason} (podprodukt: {parent_sku})",
            source=source,
            reference=reference,
        )
        if result is not None:
            updated.append(result)
    return updated
```

### `StockSyncService._apply_products` (`services/stock_sync_service.py`)
Po istniejącym wywołaniu `_apply_component_change` dodaj kaskadę:

```python
for component in components:
    updated = await self._apply_component_change(
        component=component, quantity=product.quantity, sign=sign,
        reason=reason, source=source, reference=reference,
    )
    if updated is None:
        unmatched.append(component.sku)
        continue
    if sign < 0 and updated.is_low_stock:
        low_stock.append(updated)

    cascaded = await cascade_to_sub_items(
        inventory=self._inventory,
        parent_sku=component.sku,
        change=sign * component.quantity * quantity,
        reason=reason,
        source=source,
        reference=reference,
    )
    if sign < 0:
        low_stock.extend(item for item in cascaded if item.is_low_stock)
```

Ważne: `change` przekazany do kaskady musi być **tą samą liczbą**, która
została zaaplikowana do produktu głównego (nie przeliczaj jej drugi raz
przez `component.quantity` — to już jest zrobione wcześniej w
`_apply_component_change`, więc tu trzeba policzyć identycznie:
`sign * component.quantity * quantity`).

Import na górze pliku: `from app.services.sub_item_cascade import cascade_to_sub_items`.

## 4. API (`api/schemas.py`, `api/endpoints/stock.py`)

### Schematy
```python
class StockItemOut(BaseModel):
    ...  # istniejące pola
    parent_sku: str | None = None  # NOWE

class StockSetParentIn(BaseModel):
    """Ciało żądania PUT /api/v1/stock/{sku}/parent."""
    parent_sku: str | None = None
```
Zaktualizuj `stock_item_out()` żeby mapował `item.parent_sku`.

### Nowe endpointy
```python
@router.put("/stock/{sku}/parent", response_model=StockItemOut)
async def set_stock_parent(..., sku: str, payload: StockSetParentIn) -> StockItemOut:
    """Ustawia lub czyści produkt główny dla danego SKU."""
    item = await inventory_service.set_parent(sku, payload.parent_sku)
    return stock_item_out(item)


@router.get("/stock/{sku}/sub-items", response_model=list[StockItemOut])
async def get_stock_sub_items(..., sku: str) -> list[StockItemOut]:
    """Zwraca podprodukty przypisane do produktu głównego."""
    items = await inventory_service.get_sub_items(sku)
    return [stock_item_out(i) for i in items]
```
Uwaga na kolejność tras: to musi być zadeklarowane **przed**
`GET /stock/{sku}` (ten sam problem kolejności co przy `/stock/report`,
opisany w docstringu pliku).

## 5. Desktop UI (`desktop/src/renderer/src/screens/MagazynScreen.tsx`)

### Lista magazynu (`items` tab)
- Pobierz `parent_sku` z `StockItem` (dopisz do `types/api.ts`).
- Główna tabela pokazuje wyłącznie produkty z `parent_sku === null`.
- Wiersz produktu, który jest produktem głównym (ma podprodukty — sprawdź
  frontendowo, grupując po `parent_sku`, albo doładuj `GET /stock/{sku}/sub-items`
  leniwie po rozwinięciu), dostaje badge np. „+2 podprodukty” i strzałkę
  rozwijania.
- Po rozwinięciu: wcięte podwiersze z nazwą, SKU, aktualnym stanem
  podproduktu — **tylko do odczytu** w tym miejscu, z małą notatką
  „porusza się razem z {nazwa produktu głównego}”.

### Przypisywanie podproduktu
Dodaj do istniejącego modala edycji/tworzenia produktu magazynowego (albo
nowy mały modal z poziomu wiersza — wybierz to, co lepiej pasuje do
istniejącego UX) pole „Produkt główny”: select z listy produktów, które
same nie mają podproduktów i nie są niczyim podproduktem (żeby UI od razu
wymuszał regułę jednopoziomowości — filtruj po stronie frontu, ale
backend i tak musi to twardo walidować).

### `PowiazaniaOfertView.tsx`
Nie zmieniaj mechaniki. Dopisz krótką notkę w UI (np. w opisie sekcji
„Powiązane oferty”) w stylu: „Jeśli oferta sprzedaje produkt złożony z
podproduktów (np. butelka z nakrętką i kroplomierzem), wystarczy powiązać
ją z samym produktem głównym — podprodukty odejmą się automatycznie.
Skonfiguruj je w Magazyn → edycja produktu → Produkt główny.”

## 6. Bot Telegram (opcjonalnie, spójność z resztą komend `/stock`)

Jeśli masz czas: dodaj komendę `/stock parent <sku> <parent_sku|-->`
analogiczną do `/stock link`, w `bot/handlers/stock.py`, korzystającą z
tego samego `InventoryService.set_parent`. Nieobowiązkowe dla MVP —
desktop UI wystarcza do uruchomienia funkcji.

## 7. Migracja istniejących danych (WAŻNE — nie automatyzuj na ślepo)

Jeśli w produkcji istnieją już `offer_links` z ręcznie dodanymi 3
składnikami (butelka + nakrętka + kroplomierz jako osobne wiersze w
jednej recepturze) — **nie kasuj ich automatycznie**. Po wdrożeniu tej
funkcji:
1. Użytkownik ręcznie ustawia relację produkt główny/podprodukt raz,
   dla każdej trójki produktów (Magazyn → edycja → Produkt główny).
2. Użytkownik edytuje istniejące receptury w „Powiązania ofert” tak, by
   zawierały tylko 1 składnik (produkt główny, ilość 1) zamiast 3 —
   kaskada zajmie się resztą.
3. Stary, wieloskładnikowy sposób ma pozostać technicznie możliwy (nie
   usuwaj obsługi wielu komponentów w `offer_links`) — może się przydać
   do prawdziwych zestawów łączących niezależne produkty główne.

## 8. Kryteria akceptacji

1. Produkt „Butelka 10ml” ma 2 podprodukty: „Nakrętka 10ml”, „Kroplomierz 10ml”.
   Oferta Allegro powiązana z „Butelka 10ml” (1 składnik, ilość 1) sprzedaje
   się w ilości 100 szt. → po synchronizacji stan butelki, nakrętki i
   kroplomierza spada o dokładnie 100 każdy, widoczne w historii
   (`GET /stock/{sku}/history`) z osobnymi wpisami dla każdego SKU.
2. Anulowanie/zwrot tego zamówienia przywraca wszystkie 3 stany o tyle
   samo (kaskada działa też dla `process_order_cancelled`/`process_return`,
   bo są w tej samej pętli `_apply_products`).
3. Ręczna korekta `/stock add Butelka10ml 50` (albo przez UI) zmienia
   WYŁĄCZNIE stan butelki — nakrętka i kroplomierz się nie ruszają.
   Napisz test, który to explicite sprawdza (regresja tej decyzji).
4. Próba ustawienia produktu głównego dla produktu, który sam ma
   podprodukty (albo odwrotnie) zwraca czytelny błąd 400, nie 500.
5. `GET /stock` (lista magazynowa) w desktopie pokazuje tylko produkty
   główne + samodzielne (bez `parent_sku`); podprodukty widoczne dopiero
   po rozwinięciu.
6. Test integracyjny w `backend/tests` odtwarzający scenariusz z p.1 i p.3.

## Czego NIE robić

- Nie dodawaj pola „ilość na jednostkę” dla podproduktów — zawsze 1:1
  (patrz p.1 ustaleń).
- Nie kaskaduj przy ręcznych korektach stanu (`InventoryService.*`) —
  tylko przy zdarzeniach z `StockSyncService`.
- Nie pozwalaj na więcej niż jeden poziom zagnieżdżenia — waliduj to
  twardo w `InventoryService.set_parent`, nie tylko w UI.
- Nie usuwaj ani nie zmieniaj istniejącego mechanizmu `offer_links` z
  wieloma komponentami — to osobna, dalej działająca ścieżka.
