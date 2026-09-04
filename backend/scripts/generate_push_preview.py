"""
Generator podglądu powiadomień push ORDLY.

Buduje `backend/docs/podglad-powiadomien-push.html` - jeden samodzielny
plik do otwarcia w przeglądarce, pokazujący KAŻDĄ pozycję katalogu
`push_payload.py` jako dymek powiadomienia iOS.

Po co osobne narzędzie zamiast ręcznie napisanego HTML-a: treść w tym
podglądzie pochodzi z PRAWDZIWYCH builderów katalogu, a nie z przepisanej
kopii. Dzięki temu podgląd nie może rozejść się z tym, co faktycznie
wychodzi na telefon - a to jedyna warstwa aplikacji, której nie da się
sprawdzić okiem (powiadomienie widać raz, w losowym momencie, na cudzym
ekranie blokady).

Uruchomienie (z katalogu `backend/`):

    .venv/bin/python scripts/generate_push_preview.py

Wierność wobec iOS: układ dymka odwzorowuje realny zrzut z iPhone'a -
tytuł pogrubiony i UCINANY do jednej linii, pod nim podtytuł
"from ORDLY" (Safari dokłada go sam przy Web Push z PWA), niżej treść
ucinana po czterech liniach. Szerokość dymka to 347 pt, czyli tyle, ile
na ekranie 375 pt - szerszy podgląd pokazywałby, że tytuł się mieści,
podczas gdy na telefonie już się ucina.

Ikona jest jedna dla wszystkich powiadomień - ta sama, którą pokazuje
iOS. Ikony per typ zdarzenia zostały świadomie odrzucone: iOS przy Web
Push z PWA i tak pokazuje ikonę aplikacji, więc byłby to element widoczny
wyłącznie na platformach, z których ta instalacja nie korzysta.
"""

from __future__ import annotations

import base64
import html
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND / "src"))

from app.infrastructure.webpush import push_payload  # noqa: E402
from app.infrastructure.webpush.push_payload import PushPayload  # noqa: E402

#: Prawdziwa ikona PWA (`mobile/public/icon.png`), przeskalowana do 120 px.
#: Oryginał ma 1024 px i 521 kB - wklejony w base64 rozdąłby podgląd do
#: ~700 kB przy dymku o boku 38 px, gdzie i tak nic z tej rozdzielczości
#: nie widać. To ta sama grafika, którą iOS pokazuje przy powiadomieniu.
_ICON = _BACKEND / "docs" / "assets" / "ordly-icon-120.png"
_OUTPUT = _BACKEND / "docs" / "podglad-powiadomien-push.html"

# --------------------------------------------------------------------------
# Realistyczne dane - prawdziwy asortyment tego sklepu i realne kwoty.
# --------------------------------------------------------------------------

_ZAMOWIENIE = "b2784ef0-a0c0-11f1-ae34-979fa0b8ac2d"
_ZWROT = "9f31c7aa-5512-4d0e-bd44-77aa1e2b9c31"


@dataclass(frozen=True, slots=True)
class Karta:
    """Jeden dymek w podglądzie wraz z opisem, kiedy się pojawia."""

    builder: str
    kiedy: str
    payload: PushPayload
    czas: str = "teraz"
    uwaga: str = ""


def _karty() -> list[Karta]:
    return [
        Karta(
            builder="new_order",
            kiedy="Natychmiast po wykryciu nowego zamówienia.",
            payload=push_payload.new_order(
                marketplace="allegro",
                amount=Decimal("60.94"),
                currency="PLN",
                products=[
                    (50, "Butelki PET 30 ml z zakrętką"),
                    (50, "Kroplomierze LDPE"),
                ],
                external_id=_ZAMOWIENIE,
                badge=3,
            ),
        ),
        Karta(
            builder="many_new_orders",
            kiedy="Gdy jedna synchronizacja przyniesie kilka zamówień naraz.",
            payload=push_payload.many_new_orders(
                count=4,
                per_channel={"allegro": 3, "olx": 1},
                total_amount=Decimal("1284.50"),
                currency="PLN",
                badge=4,
            ),
        ),
        Karta(
            builder="low_stock",
            kiedy="Gdy stan produktu spadnie do progu minimalnego.",
            payload=push_payload.low_stock(
                name="Butelki PET 30 ml bursztynowe",
                sku="PET30-BUR",
                stock=14,
                min_stock=20,
            ),
        ),
        Karta(
            builder="unmatched_products",
            kiedy="Gdy sprzedana pozycja nie ma powiązania z magazynem.",
            payload=push_payload.unmatched_products(
                reference=_ZAMOWIENIE,
                product_names=[
                    "Butelki PET 30 ml z zakrętką",
                    "Nakrętki DIN18 czarne z plombą",
                    "Kroplomierze LDPE 0,8 mm",
                ],
            ),
            uwaga=(
                "To zdarzenie szło wcześniej na telefon wspólną ścieżką z Telegramem "
                "i pokazywało dosłowne <b> oraz <code> na ekranie blokady. Telegram "
                "nadal dostaje pełny format z komendą do skopiowania."
            ),
        ),
        Karta(
            builder="new_dispute",
            kiedy="Gdy kupujący rozpocznie dyskusję (z powiadomienia e-mail Allegro).",
            payload=push_payload.new_dispute(
                buyer_login="Rexpiot",
                reason="niezgodny z opisem",
                respond_by=datetime(2026, 7, 29, 8, 41),
                issue_id="81ecd951-ab12-4528-8154-af5699df2b1c",
                badge=1,
            ),
            uwaga=(
                "Termin odpowiedzi pochodzi WYŁĄCZNIE z maila - API Allegro go nie "
                "zwraca. Dlatego to jedyne zdarzenie z Allegro.pl czytane ze skrzynki."
            ),
        ),
        Karta(
            builder="new_return",
            kiedy="Gdy kupujący zgłosi zwrot wymagający decyzji.",
            payload=push_payload.new_return(
                external_id=_ZWROT,
                products_summary="Kroplomierze LDPE 0,8 mm x10",
                reason="uszkodzenie w transporcie",
                badge=1,
            ),
        ),
        Karta(
            builder="pending_packing",
            kiedy="Raz dziennie o 9:00, jeśli coś czeka na spakowanie.",
            payload=push_payload.pending_packing(
                count=3, oldest_since="wczoraj 17:40", badge=3
            ),
            czas="9:00",
        ),
        Karta(
            builder="sync_failed",
            kiedy="Dopiero po DRUGIEJ nieudanej próbie synchronizacji z rzędu.",
            payload=push_payload.sync_failed(channel="allegro", retry_in_minutes=5),
        ),
        Karta(
            builder="wholesaler_confirmed",
            kiedy="Gdy hurtownia odpisze na zamówienie. CICHE z definicji.",
            payload=push_payload.wholesaler_confirmed(
                wholesaler_name="Pako-Plast",
                items_summary="1000x butelka PET 30 ml — wysyłka jutro",
            ),
            czas="14:20",
        ),
        Karta(
            builder="allegro_lokalnie_event",
            kiedy="Gdy przyjdzie powiadomienie e-mail z Allegro Lokalnie (kanał bez API).",
            payload=push_payload.allegro_lokalnie_event(
                event_type="new_order",
                # Dane z REALNEGO maila: tests/fixtures/allegro_lokalnie/
                # "Sprzedano 100szt. Butelka Gorilla 10ml…"
                listing_title=(
                    "100szt. Butelka Gorilla 10ml Liquid Aromat Baza olejki DIY kosmetyki PET"
                ),
                quantity=4,
                amount=Decimal("287.92"),
                message_id="<notificationstwo.20260811163208@allegro.pl>",
            ),
            uwaga=(
                "Kwota to suma zapłacona przez kupującego (4 × 71,98 zł), nie cena "
                "jednostkowa ogłoszenia. Nazwa kanału jest w treści i bez skrótu - "
                "w tytule ucinała się na „Allegro Lok…”."
            ),
        ),
        Karta(
            builder="allegro_lokalnie_event (zwrot)",
            kiedy="Gdy mail z Allegro Lokalnie dotyczy zwrotu albo reklamacji.",
            payload=push_payload.allegro_lokalnie_event(
                event_type="return",
                listing_title=(
                    "25szt. Butelka Gorilla 60ml Liquid Aromat Baza olejki DIY kosmetyki PET"
                ),
                quantity=1,
                amount=Decimal("71.98"),
                message_id="<notificationsthree.20260901101500@allegro.pl>",
            ),
            uwaga=(
                "Ten sam builder co wyżej, inny typ zdarzenia. Zwrot był dotąd "
                "wrzucony do „Zmiana zamówienia” razem z „paczka dostarczona” i "
                "„anulowano” - a jako jedyny z tej trójki wymaga reakcji, więc ma "
                "teraz własny tytuł."
            ),
            czas="10:15",
        ),
        Karta(
            builder="olx_event (sprzedaż)",
            kiedy="Gdy ktoś kupi Twoje ogłoszenie z Przesyłką OLX.",
            payload=push_payload.olx_event(
                event_type="new_order",
                # Dane z REALNEGO maila: tests/fixtures/olx/
                # "Kupujacy juz zaplacil, potwierdz sprzedaz do 15_29 16-12-2025"
                opis="5x Butelka Gorilla 60ml Każda Ilość | Na Liquid Aromat Klej Tusz | DIY",
                message_id="<0102019b181eba89-5cdc713d@eu-west-1.amazonses.com>",
            ),
            uwaga=(
                "Bez kwoty i bez słowa „zamówienie”, bo zamówienie w ORDLY z tego NIE "
                "powstaje: mail z OLX nie podaje ceny ani sumy zapłaconej. Stąd „stan "
                "bez zmian” w treści - magazyn poprawiasz ręcznie i to jedyne miejsce, "
                "gdzie ta informacja trafia na ekran blokady."
            ),
            czas="15:29",
        ),
        Karta(
            builder="olx_event (wiadomość)",
            kiedy="Gdy kupujący napisze w sprawie ogłoszenia.",
            payload=push_payload.olx_event(
                event_type="new_message",
                opis="Butelki PET 10 ml do liquidów – zestaw 10 szt. + dozownik + zakrętka",
                message_id="<010201a048a929c9-47b08d7c@eu-west-1.amazonses.com>",
            ),
            uwaga=(
                "Nazwa kanału ZOSTAJE w tytule, odwrotnie niż przy Allegro Lokalnie: "
                "„OLX” to trzy znaki, więc nic się nie ucina. Treścią jest tytuł "
                "ogłoszenia, bo temat maila jest dla wszystkich wiadomości z OLX "
                "identyczny („Wiadomości dotyczące ogłoszeń”) i sam z siebie nie mówi nic."
            ),
            czas="13:57",
        ),
    ]


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------

_STYL = """
:root {
  --tekst: #f5f8f6;
  --tekst-drugi: rgba(235, 242, 238, 0.62);
  --dymek: rgba(64, 66, 74, 0.55);
  --dymek-krawedz: rgba(255, 255, 255, 0.11);
  --akcent: #5fd9cc;
  --uwaga: #f5c065;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 40px 20px 80px;
  background:
    radial-gradient(1100px 620px at 18% -8%, #3d2f4d 0%, transparent 62%),
    radial-gradient(900px 520px at 88% 8%, #5a2f36 0%, transparent 58%),
    linear-gradient(180deg, #14121c 0%, #241a20 52%, #3a2119 100%);
  background-attachment: fixed;
  color: var(--tekst);
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
}
.strona { max-width: 1180px; margin: 0 auto; }
header { text-align: center; margin-bottom: 34px; }
h1 { font-size: 25px; font-weight: 700; margin: 0 0 8px; letter-spacing: -0.4px; }
.podtytul {
  font-size: 13.5px; line-height: 1.6; color: var(--tekst-drugi);
  max-width: 730px; margin: 0 auto;
}
.zasada {
  border: 1px solid rgba(95, 217, 204, 0.28);
  background: rgba(95, 217, 204, 0.06);
  border-radius: 12px; padding: 14px 16px; margin: 26px auto 34px;
  font-size: 12.5px; line-height: 1.68; color: rgba(235, 242, 238, 0.82);
  max-width: 800px; text-align: left;
}
.zasada b { color: var(--akcent); }
.siatka {
  display: grid; gap: 26px;
  grid-template-columns: repeat(auto-fill, minmax(370px, 1fr));
  align-items: start;
}
.karta { display: flex; flex-direction: column; gap: 9px; }
.etykieta {
  display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap;
  font-size: 11px; color: var(--tekst-drugi);
}
.etykieta code {
  font-family: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace;
  font-size: 11px; color: var(--tekst);
  background: rgba(255, 255, 255, 0.09);
  padding: 2px 7px; border-radius: 5px;
}
.znacznik {
  font-size: 9.5px; font-weight: 700; letter-spacing: 0.06em;
  text-transform: uppercase; padding: 2px 7px; border-radius: 999px;
  background: rgba(255, 255, 255, 0.1); color: var(--tekst-drugi);
}

/* Dymek 1:1 z realnym zrzutem z iPhone'a.
   `max-width` to NIE jest ozdobnik: na ekranie 375 pt dymek ma ~347 pt.
   Szerszy podgląd pokazywałby, że tytuł się mieści, podczas gdy na
   telefonie już się ucina - czyli kłamałby dokładnie w tej sprawie,
   dla której powstał. */
.dymek {
  display: flex; gap: 11px; align-items: flex-start;
  max-width: 347px;
  padding: 12px 13px;
  background: var(--dymek);
  border: 1px solid var(--dymek-krawedz);
  border-radius: 21px;
  backdrop-filter: blur(28px) saturate(150%);
  -webkit-backdrop-filter: blur(28px) saturate(150%);
  box-shadow: 0 10px 26px rgba(0, 0, 0, 0.3);
}
.ikona {
  width: 38px; height: 38px; border-radius: 9px; flex: 0 0 38px;
  object-fit: cover; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
}
.tresc { min-width: 0; flex: 1; }
.gora { display: flex; align-items: baseline; gap: 10px; }
/* Tytuł jest UCINANY do jednej linii - dokładnie jak na iOS. */
.tytul {
  font-size: 15px; font-weight: 700; line-height: 1.25; letter-spacing: -0.2px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1;
}
.czas { font-size: 13px; color: var(--tekst-drugi); flex: 0 0 auto; }
/* Podtytuł, który Safari dokłada sam przy Web Push z PWA. */
.zrodlo { font-size: 15px; font-weight: 600; color: var(--tekst-drugi); line-height: 1.3; }
.body {
  font-size: 15px; line-height: 1.32; margin-top: 1px; white-space: pre-wrap;
  display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical;
  overflow: hidden;
}
.pod-dymkiem { font-size: 11.5px; line-height: 1.6; color: var(--tekst-drugi); }
.pod-dymkiem b { color: var(--tekst); font-weight: 600; }
.uwaga {
  border-left: 2px solid var(--uwaga); padding-left: 9px;
  color: rgba(245, 192, 101, 0.92);
}
footer {
  margin-top: 54px; padding-top: 20px; font-size: 11.5px; line-height: 1.7;
  color: var(--tekst-drugi); border-top: 1px solid rgba(255, 255, 255, 0.1);
}
"""


def _dymek(karta: Karta, icon_data_uri: str) -> str:
    """Renderuje jeden dymek + opis pod nim."""
    payload = karta.payload
    ciche = '<span class="znacznik">ciche</span>' if payload.silent else ""
    uwaga = (
        f'<p class="pod-dymkiem uwaga">{html.escape(karta.uwaga)}</p>' if karta.uwaga else ""
    )

    return f"""
      <article class="karta">
        <div class="etykieta"><code>{html.escape(karta.builder)}</code>{ciche}</div>
        <div class="dymek">
          <img class="ikona" src="{icon_data_uri}" alt="">
          <div class="tresc">
            <div class="gora">
              <div class="tytul">{html.escape(payload.title)}</div>
              <div class="czas">{html.escape(karta.czas)}</div>
            </div>
            <div class="zrodlo">from ORDLY</div>
            <div class="body">{html.escape(payload.body)}</div>
          </div>
        </div>
        <p class="pod-dymkiem">{html.escape(karta.kiedy)}</p>
        <p class="pod-dymkiem"><b>Otwiera:</b> <code>{html.escape(payload.url)}</code>
           · <b>wątek:</b> {html.escape(payload.thread)}</p>
        {uwaga}
      </article>"""


def build_html() -> str:
    """Składa cały podgląd - jeden plik, bez zależności sieciowych."""
    icon_data_uri = "data:image/png;base64," + base64.b64encode(_ICON.read_bytes()).decode()
    karty = _karty()
    katalog = "\n".join(_dymek(karta, icon_data_uri) for karta in karty)

    return f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ORDLY — podgląd powiadomień push</title>
<style>{_STYL}</style>
</head>
<body>
<div class="strona">
  <header>
    <h1>Powiadomienia push ORDLY</h1>
    <p class="podtytul">
      Każdy dymek jest zbudowany z PRAWDZIWEGO kodu katalogu
      (<code>push_payload.py</code>), nie z przepisanej kopii — podgląd nie może
      rozejść się z tym, co faktycznie wychodzi na telefon. Układ odwzorowuje
      realny zrzut z iPhone'a: dymek 347 pt, tytuł ucinany do jednej linii,
      podtytuł „from ORDLY” dokładany przez Safari, treść ucinana po czterech liniach.
    </p>
    <div class="zasada">
      <b>Zasada treści:</b> powiadomienie mówi <b>ile, czego i za ile</b> — tyle,
      żeby zdecydować, czy otwierać aplikację. Wszystko, co służy dopiero działaniu
      (login kupującego, pełny numer zamówienia, numer zwrotu, treść pytania,
      instrukcja z komendą bota) zostaje w apce, do której prowadzi kliknięcie.<br><br>
      <b>Zasada kanału:</b> treść formatuje KANAŁ, nie miejsce zdarzenia. Telegram
      renderuje HTML i dostaje pogrubienia oraz <code>&lt;code&gt;</code> z komendą
      do skopiowania; Web Push HTML-a nie renderuje, więc dostaje czysty tekst
      z tego katalogu. Wspólna ścieżka <code>send_text</code> dodatkowo przepuszcza
      treść przez <code>strip_html</code> — na wypadek, gdyby ktoś w przyszłości
      wysłał tędy tekst pisany pod Telegram.<br><br>
      <b>Ikona:</b> jedna dla wszystkich powiadomień, ta sama co ikona aplikacji.
      Ikony per typ zdarzenia zostały odrzucone — iOS przy Web Push z PWA i tak
      pokazuje ikonę aplikacji, więc byłby to element widoczny wyłącznie tam,
      gdzie ORDLY nie jest używany.
    </div>
  </header>

  <div class="siatka">{katalog}
  </div>

  <footer>
    Plik wygenerowany przez <code>backend/scripts/generate_push_preview.py</code>.
    Po każdej zmianie treści powiadomień uruchom go ponownie, zamiast poprawiać
    ten HTML ręcznie — inaczej podgląd zacznie kłamać.
  </footer>
</div>
</body>
</html>
"""


def main() -> None:
    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(build_html(), encoding="utf-8")
    rozmiar = _OUTPUT.stat().st_size / 1024
    print(f"Zapisano {_OUTPUT} ({rozmiar:.0f} kB)")


if __name__ == "__main__":
    main()
