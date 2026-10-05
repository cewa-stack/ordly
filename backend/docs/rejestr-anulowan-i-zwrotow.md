# Rejestr anulowań i zwrotów pieniędzy

Jeden rekord na zamówienie (kanał i numer zamówienia), w którym zamówienie anulowano albo oddano pieniądze. Kod: `app/domain/customer_cases.py`, tabela `customer_cases` (migracja 0016).

## Co jest zapisywane

| Pole | Skąd |
|---|---|
| numer zamówienia, ID zamówienia w Allegro | synchronizacja (dla Allegro.pl to ten sam numer) |
| rodzaj: anulowanie / zwrot pieniędzy / oba | zdarzenie, które utworzyło lub uzupełniło rekord |
| data złożenia zamówienia | `orders.order_date` (pierwsze zobaczenie zamówienia) |
| data anulowania | chwila wykrycia anulowania (synchronizacja albo ręczny status „Anulowane”) |
| data zwrotu pieniędzy | chwila wykrycia, że zwrot przeszedł w „pieniądze oddane” |
| powód | z Allegro tylko dla zwrotów (kod powodu podany przez kupującego); dla anulowań wpisywany ręcznie na desktopie |
| status obsługi | Zgłoszony / W trakcie realizacji / Zakończony |
| źródło zdarzenia | Allegro - anulowanie, Allegro - zwrot klienta, status w aplikacji, dane sprzed wdrożenia |
| login Allegro kupującego | checkout-form albo zwrot klienta |

Brak danej oznacza „nieuzupełnione” (`null`). Zaślepka „nieznany” nie trafia do rekordu jako login.

## Czego celowo NIE zapisujemy

Rekord nie zawiera numeru telefonu, adresu e-mail ani imienia i nazwiska kupującego. Pomija też wolny komentarz kupującego do zwrotu (`reason.userComment`). To decyzja właściciela z 2026-10-04 (D7: zbieranie tych danych do późniejszego kontaktu uznał za niezgodne z prawem). Klienta identyfikuje login Allegro, a kontakt odbywa się przez Allegro, po numerze zamówienia.

## Zasady

- Ponowne wykrycie tego samego zamówienia uzupełnia rekord, ale nie tworzy duplikatu (unikalny klucz kanał + numer).
- Pusta wartość nigdy nie nadpisuje uzupełnionej. Powód wpisany ręcznie nie jest nadpisywany powodem z Allegro.
- Każda zmiana powodu trafia do `customer_case_reason_changes` (kiedy, skąd, z czego na co).
- Dostęp tylko przez ORDLY API z tokenem (`/api/v1/customer-cases`). Login nie trafia do logów Loguru, Telegrama ani powiadomień push.
- Rekordy sprzed wdrożenia (migracja) mają źródło „Dane sprzed wdrożenia”, status obsługi „Zakończony” oraz puste daty anulowania i zwrotu.
