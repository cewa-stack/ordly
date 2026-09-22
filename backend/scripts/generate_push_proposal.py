"""
Projekt powiadomień push dopasowanych do redesignu "Nokturn".

Buduje `backend/docs/projekt-powiadomien-push-nokturn.html` - podgląd DO
AKCEPTACJI. Obok leży `podglad-powiadomien-push.html`, który dalej
pokazuje to, co jest dziś wdrożone; ten plik pokazuje, co się zmieni.

Reguła katalogu zostaje zachowana: KAŻDY dymek pochodzi z prawdziwego
kodu, także w kolumnie "przed". Anulowane zamówienie jest dziś budowane
wprost w `WebPushNotifier`, poza katalogiem - dlatego kolumnę "przed"
bierzemy z samego notifiera, przechwytując jego wysyłkę, zamiast
przepisywać jego treść ręcznie.

Uruchomienie (z katalogu `backend/`):

    .venv/bin/python scripts/generate_push_proposal.py
"""

from __future__ import annotations

import asyncio
import base64
import html
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_ROOT = _BACKEND.parent
sys.path.insert(0, str(_BACKEND / "src"))

from app.domain.entities.customer import Customer  # noqa: E402
from app.domain.entities.order import Order  # noqa: E402
from app.domain.entities.product import Product  # noqa: E402
from app.infrastructure.webpush import push_payload as p  # noqa: E402
from app.infrastructure.webpush.push_payload import PushPayload  # noqa: E402
from app.infrastructure.webpush.web_push_notifier import WebPushNotifier  # noqa: E402

_OUTPUT = _BACKEND / "docs" / "projekt-powiadomien-push-nokturn.html"
#: Nowa ikona aplikacji - ta sama, którą iOS pokaże przy KAŻDYM powiadomieniu.
_ICON = _ROOT / "mobile" / "public" / "apple-touch-icon.png"

_NOW = datetime(2026, 9, 22, 9, 0)
_ZAMOWIENIE = "b2784ef0-a0c0-11f1-ae34-979fa0b8ac2d"


# ----------------------------------------------------------------------
# "Przed" z prawdziwego kodu
# ----------------------------------------------------------------------


class _Przechwyt(WebPushNotifier):
    """Notifier, który zamiast wysyłać - zapamiętuje payload."""

    def __init__(self) -> None:  # noqa: D107 - bez sesji i VAPID, niczego nie wysyła
        self.zlapane: list[PushPayload] = []

    async def _send(self, payload: PushPayload, *, respect_quiet_hours: bool = True):  # type: ignore[override]
        self.zlapane.append(payload)


def _dzisiejsze_anulowane() -> PushPayload:
    """Treść anulowania dokładnie taka, jaką buduje dziś `WebPushNotifier`."""
    order = Order(
        external_id=_ZAMOWIENIE,
        marketplace="allegro",
        buyer=Customer(login="Kupiec99", email="kupiec@example.com"),
        products=[Product(external_id="P1", name="Butelki PET 30 ml", quantity=50,
                          unit_price=Decimal("0.61"))],
        total_amount=Decimal("30.50"),
        currency="PLN",
        status="CANCELLED",
        order_date=datetime(2026, 9, 21, 15, 40),
    )
    przechwyt = _Przechwyt()
    asyncio.run(przechwyt.notify_order_cancelled(order))
    return przechwyt.zlapane[0]


def _dzisiejsze_przypomnienie() -> PushPayload:
    """
    Przypomnienie o 9:00 TAK, JAK LICZY JE DZIŚ KOD: `order_date` jest
    zapisane w UTC, a `WebPushNotifier` formatuje je przez `strftime`
    bez przeliczenia. Zamówienie z wczoraj 17:40 czasu polskiego to
    15:40 UTC - i to widzi dziś użytkownik.
    """
    oldest_utc = datetime(2026, 9, 21, 15, 40)
    return p.pending_packing(count=3, oldest_since=oldest_utc.strftime("%H:%M"), badge=3)


# ----------------------------------------------------------------------
# Model podglądu
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Zmiana:
    tytul: str
    przed: PushPayload | None
    po: PushPayload
    dlaczego: str
    czas: str = "teraz"
    przed_opis: str = ""


def _zmiany() -> list[Zmiana]:
    brief = p.morning_brief(
        pending_count=3,
        oldest_local=datetime(2026, 9, 21, 17, 40),
        now_local=_NOW,
        open_issues=2,
        open_returns=1,
        badge=p.attention_badge(pending=3, open_issues=2, open_returns=1),
    )
    assert brief is not None
    return [
        Zmiana(
            tytul="Przypomnienie o 9:00 → poranny raport",
            przed=_dzisiejsze_przypomnienie(),
            po=brief,
            czas="9:00",
            dlaczego=(
                "BŁĄD: godzina najstarszego zamówienia jest dziś w UTC — latem cofnięta "
                "o 2 h (zamówienie z 17:40 pokazuje się jako „od 15:40”) i bez słowa "
                "„wczoraj”. Poza tym przypomnienie mówiło tylko o paczkach, choć rano "
                "czekają też dyskusje i zwroty. Raport mówi o wszystkim naraz, liczy "
                "godzinę lokalnie i otwiera ekran Start — ten, na którym widać "
                "dokładnie te same trzy liczby."
            ),
        ),
        Zmiana(
            tytul="Zamówienie anulowane",
            przed=_dzisiejsze_anulowane(),
            po=p.order_cancelled(
                marketplace="allegro",
                amount=Decimal("30.50"),
                currency="PLN",
                products=[(50, "Butelki PET 30 ml")],
                external_id=_ZAMOWIENIE,
            ),
            czas="16:12",
            dlaczego=(
                "Treść budowana dotąd poza katalogiem, dlatego nie było jej w podglądzie. "
                "Pokazywała login kupującego na ekranie blokady (wbrew zasadzie katalogu) "
                "i nie mówiła, ile to było warte. Teraz ten sam układ co „Nowe "
                "zamówienie” — kanał, co, za ile. Zostaje CICHE: anulowanie niczego od "
                "Ciebie nie wymaga."
            ),
        ),
        Zmiana(
            tytul="Allegro Lokalnie: zmiana zamówienia (doręczono, anulowano)",
            przed=p.allegro_lokalnie_event(
                event_type="order_status",
                listing_title="100szt. Butelka Gorilla 10ml Liquid Aromat Baza olejki DIY",
                quantity=4,
                amount=Decimal("287.92"),
                message_id="<a@allegro.pl>",
            ),
            po=p.allegro_lokalnie_event(
                event_type="order_status",
                listing_title="100szt. Butelka Gorilla 10ml Liquid Aromat Baza olejki DIY",
                quantity=4,
                amount=Decimal("287.92"),
                message_id="<a@allegro.pl>",
                silent=True,
            ),
            czas="12:05",
            dlaczego=(
                "Treść bez zmian — zmienia się DŹWIĘK. Własny komentarz w katalogu mówi, "
                "że doręczenie i anulowanie „nie wymagają żadnej reakcji”, a dziś dzwonią "
                "tak samo jak sprzedaż. Zasada z aplikacji: rzeczy skończone nie świecą — "
                "w powiadomieniach znaczy to, że nie dzwonią. Zwrot z tego kanału ma "
                "osobny tytuł i DZWONI dalej."
            ),
        ),
        Zmiana(
            tytul="Test powiadomień (Ustawienia → Wyślij test)",
            przed=PushPayload(
                title="ORDLY",
                body="To jest testowe powiadomienie z ORDLY.",
                thread="sync",
                url="/settings",
            ),
            po=p.test_notification(),
            przed_opis=(
                "„Przed” to jedyny dymek złożony tu ręcznie: treść testu żyje dziś "
                "w endpoincie, nie w katalogu."
            ),
            dlaczego=(
                "Dziś słowo ORDLY pada trzy razy: w tytule, w podpisie „from ORDLY”, "
                "który Safari dokłada sam, i w treści. Tytuł ma powiedzieć, co "
                "sprawdzasz — że powiadomienia działają."
            ),
        ),
    ]


def _bez_zmian() -> list[tuple[str, PushPayload, str]]:
    return [
        ("new_order", p.new_order(
            marketplace="allegro", amount=Decimal("60.94"), currency="PLN",
            products=[(50, "Butelki PET 30 ml z zakrętką"), (50, "Kroplomierze LDPE")],
            external_id=_ZAMOWIENIE), "11:42"),
        ("many_new_orders", p.many_new_orders(
            count=4, per_channel={"allegro": 3, "olx": 1},
            total_amount=Decimal("1284.50"), currency="PLN"), "teraz"),
        ("new_dispute", p.new_dispute(
            buyer_login="Kupiec99", reason="niezgodny z opisem",
            respond_by=datetime(2026, 9, 29, 8, 41),
            issue_id="81ecd951-ab12-4528-8154-af5699df2b1c"), "10:18"),
        ("new_return", p.new_return(
            external_id="9f31c7aa", products_summary="Kroplomierze LDPE 0,8 mm x10",
            reason="uszkodzenie w transporcie"), "8:55"),
        ("olx_event", p.olx_event(
            event_type="new_message",
            opis="Butelki PET 10 ml do liquidów – zestaw 10 szt. + dozownik",
            message_id="<x@amazonses.com>"), "13:57"),
        ("wholesaler_confirmed", p.wholesaler_confirmed(
            wholesaler_name="Pako-Plast",
            items_summary="1000x butelka PET 30 ml — wysyłka jutro"), "14:20"),
        ("mailbox_unavailable", p.mailbox_unavailable(
            login_rejected=True, retry_in_minutes=5), "teraz"),
    ]


# ----------------------------------------------------------------------
# Render
# ----------------------------------------------------------------------


def _dymek(payload: PushPayload, czas: str, ikona: str, *, ciemny: bool = True) -> str:
    dzwiek = (
        '<span class="dzw cichy">cicho</span>' if payload.silent
        else '<span class="dzw">dźwięk</span>'
    )
    return f"""
      <div class="dymek{' jasny' if not ciemny else ''}">
        <img class="ikona" src="{ikona}" alt="">
        <div class="tresc">
          <div class="gora"><div class="tytul">{html.escape(payload.title)}</div>
            <div class="czas">{html.escape(czas)}</div></div>
          <div class="zrodlo">from ORDLY</div>
          <div class="body">{html.escape(payload.body)}</div>
        </div>
      </div>
      <div class="meta">{dzwiek}<code>{html.escape(payload.url)}</code>
        <span>plakietka: {'bez zmian' if payload.badge is None else payload.badge}</span></div>"""


_STYL = """
:root{--void:#060D0C;--base:#0A1413;--panel:#101D1B;--panel2:#162724;--line:rgba(214,235,228,.075);
--line2:rgba(214,235,228,.15);--tx:#EAF3EF;--tx2:#93A9A3;--tx3:#6F8882;--teal:#5FD9CC;
--glow:rgba(95,217,204,.16);--coral:#FF8563;--coralg:rgba(255,133,99,.14);--amber:#F5C065}
*{box-sizing:border-box}
body{margin:0;background:var(--void);color:var(--tx);
 font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,sans-serif;
 -webkit-font-smoothing:antialiased}
body::before{content:"";position:fixed;inset:0;pointer-events:none;
 background:radial-gradient(900px 460px at 18% -8%,rgba(31,125,128,.22),transparent 62%),
 radial-gradient(700px 400px at 88% 2%,rgba(126,139,255,.10),transparent 60%)}
.strona{position:relative;max-width:1160px;margin:0 auto;padding:44px 16px 90px}
@media(min-width:700px){.strona{padding:44px 22px 90px}}
.eyebrow{font:500 10.5px ui-monospace,"JetBrains Mono",Menlo,monospace;letter-spacing:.15em;
 text-transform:uppercase;color:var(--tx3)}
h1{font-size:30px;letter-spacing:-.03em;margin:8px 0 10px}
h1 span{color:var(--teal)}
h2{font-size:19px;letter-spacing:-.02em;margin:0 0 6px}
.lead{max-width:760px;color:var(--tx2);font-size:14px;line-height:1.6;margin:0}
section{margin-top:44px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:20px 22px}
.szczera{border-left:2px solid var(--amber);padding:12px 16px;margin-top:22px;max-width:820px;
 background:rgba(245,192,101,.06);border-radius:0 12px 12px 0;font-size:13px;line-height:1.65;color:var(--tx2)}
.szczera b{color:var(--amber)}
.dwie{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(360px,100%),1fr));gap:22px;align-items:start}
.kol-etykieta{font:600 11px ui-monospace,Menlo,monospace;letter-spacing:.12em;text-transform:uppercase;
 margin-bottom:10px;color:var(--tx3)}
.kol-etykieta.po{color:var(--teal)}
.dymek{display:flex;gap:11px;align-items:flex-start;max-width:347px;padding:12px 13px;
 background:rgba(64,66,74,.62);border:1px solid rgba(255,255,255,.11);border-radius:21px;
 backdrop-filter:blur(28px) saturate(150%);box-shadow:0 10px 26px rgba(0,0,0,.3)}
.ikona{width:38px;height:38px;border-radius:9px;flex:0 0 38px}
.tresc{min-width:0;flex:1}
.gora{display:flex;gap:10px;align-items:baseline}
.tytul{font:700 15px/1.25 inherit;letter-spacing:-.2px;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.czas{font-size:13px;color:rgba(235,242,238,.62)}
.zrodlo{font-size:15px;font-weight:600;color:rgba(235,242,238,.62);line-height:1.3}
.body{font-size:15px;line-height:1.32;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.meta{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:9px 0 0 4px;font-size:11px;color:var(--tx3)}
.meta code{font-family:ui-monospace,Menlo,monospace;color:var(--tx2);overflow-wrap:anywhere}
code{overflow-wrap:anywhere}
.dzw{font-weight:700;font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;padding:2px 8px;
 border-radius:999px;background:var(--coralg);color:var(--coral)}
.dzw.cichy{background:rgba(147,169,163,.12);color:var(--tx3)}
.dlaczego{margin:14px 0 0;font-size:13px;line-height:1.62;color:var(--tx2);max-width:760px}
.brak{font-size:12.5px;color:var(--tx3);font-style:italic}
.zmiana{padding:22px;margin-top:18px}
.zmiana h3{font-size:15px;margin:0 0 16px;letter-spacing:-.01em}
.ekrany{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(403px,100%),1fr));gap:26px;margin-top:20px}
/* Makieta 1:1: ekran 375 pt, dymek 347 pt, tekst w prawdziwych rozmiarach.
   Wezsza makieta albo mniejsza czcionka pokazywalyby, ze tytul sie ucina,
   choc na telefonie sie miesci - a to jedyna rzecz, ktora ten podglad
   ma mowic prawdziwie. Na waskim oknie przegladarki cala makieta sie
   skaluje (zoom), zamiast przelamywac tekst inaczej niz iPhone. */
.telefon{width:403px;height:840px;border-radius:54px;padding:14px;background:#000;
 box-shadow:0 0 0 2px #2a2f33,0 30px 70px -30px rgba(0,0,0,.9);margin:0 auto;flex:none}
.skala{display:flex;justify-content:center}
@media(max-width:470px){.skala{zoom:.78}}
@media(max-width:360px){.skala{zoom:.64}}
.ekran{position:relative;height:100%;border-radius:40px;overflow:hidden;
 background:radial-gradient(420px 320px at 20% 0%,#2c6f6c,transparent 70%),
 linear-gradient(180deg,#123330,#0a1413 60%,#060d0c)}
.zegar{text-align:center;padding-top:58px;font-size:82px;font-weight:600;letter-spacing:-2px;color:#EAF3EF}
.data{text-align:center;font-size:19px;font-weight:600;color:rgba(234,243,239,.8)}
.stos{position:absolute;left:14px;right:14px;bottom:26px;display:flex;flex-direction:column;gap:8px}
.stos .dymek{max-width:347px}
.stos .zrodlo{display:none}
.stos .cicha{opacity:.72}
.dom{padding:70px 26px 0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:26px 18px}
.app{display:flex;flex-direction:column;align-items:center;gap:6px;font-size:11px;color:#EAF3EF}
.app i{display:block;width:min(60px,100%);aspect-ratio:1;border-radius:14px;background:rgba(255,255,255,.13)}
.app .ordly{position:relative;width:min(60px,100%);aspect-ratio:1}
.app .ordly img{width:100%;height:100%;border-radius:14px}
.app .ordly b{position:absolute;top:-6px;right:-7px;min-width:22px;height:22px;border-radius:11px;
 background:#FF3B30;color:#fff;font-size:13px;display:flex;align-items:center;justify-content:center;padding:0 6px}
.start{padding:22px}
.kafle{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}
.kafel{border:1px solid var(--line);border-radius:18px;background:var(--panel);padding:13px 14px}
.kafel .l{font:500 9px ui-monospace,Menlo,monospace;letter-spacing:.15em;text-transform:uppercase;color:var(--tx3)}
.kafel .l::before{content:"";display:inline-block;width:5px;height:5px;border-radius:3px;margin-right:6px;vertical-align:middle;background:var(--k)}
.kafel .v{font-size:26px;font-weight:700;letter-spacing:-.03em;margin-top:6px}
.suma{margin-top:14px;font-size:13px;color:var(--tx2);line-height:1.6}
.suma b{color:var(--tx)}
table{width:100%;border-collapse:collapse;font-size:13px}
.panel:has(table){overflow-x:auto}
th{text-align:left;font:500 10px ui-monospace,Menlo,monospace;letter-spacing:.14em;text-transform:uppercase;
 color:var(--tx3);padding:10px 12px;border-bottom:1px solid var(--line2)}
td{padding:12px;border-bottom:1px solid var(--line);vertical-align:top;line-height:1.5;color:var(--tx2)}
td:first-child{color:var(--tx);font-weight:600;white-space:nowrap}
.siatka{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(360px,100%),1fr));gap:22px}
.etyk{font:500 11px ui-monospace,Menlo,monospace;color:var(--tx3);margin-bottom:8px}
ol.decyzje{margin:0;padding-left:22px;line-height:1.75;font-size:14px;color:var(--tx2)}
ol.decyzje b{color:var(--tx)}
footer{margin-top:60px;padding-top:18px;border-top:1px solid var(--line);font-size:11.5px;color:var(--tx3);line-height:1.7}
"""


def build_html() -> str:
    ikona = "data:image/png;base64," + base64.b64encode(_ICON.read_bytes()).decode()
    zmiany = _zmiany()
    bez = _bez_zmian()
    brief = zmiany[0].po
    badge = p.attention_badge(pending=3, open_issues=2, open_returns=1)

    sekcja_zmian = ""
    for z in zmiany:
        przed = (
            _dymek(z.przed, z.czas, ikona) if z.przed is not None
            else '<p class="brak">Dziś nie ma takiego powiadomienia.</p>'
        )
        opis = f'<p class="dlaczego"><i>{html.escape(z.przed_opis)}</i></p>' if z.przed_opis else ""
        sekcja_zmian += f"""
    <div class="panel zmiana">
      <h3>{html.escape(z.tytul)}</h3>
      <div class="dwie">
        <div><div class="kol-etykieta">Dziś</div>{przed}</div>
        <div><div class="kol-etykieta po">Po zmianie</div>{_dymek(z.po, z.czas, ikona)}</div>
      </div>
      <p class="dlaczego">{html.escape(z.dlaczego)}</p>{opis}
    </div>"""

    # Ekran blokady - realistyczny dzień, najnowsze na górze.
    dzien = [
        (p.order_cancelled(marketplace="allegro", amount=Decimal("30.50"), currency="PLN",
                           products=[(50, "Butelki PET 30 ml")], external_id="x"), "16:12"),
        (bez[5][1], "14:20"),
        (bez[4][1], "13:57"),
        (bez[0][1], "11:42"),
        (brief, "9:00"),
    ]
    stos = "".join(
        f'<div class="{"cicha" if pl.silent else ""}">'
        + _dymek(pl, czas, ikona).split('<div class="meta">')[0]
        + "</div>"
        for pl, czas in dzien
    )

    reszta = "".join(
        f'<div><div class="etyk">{html.escape(nazwa)}</div>{_dymek(pl, czas, ikona)}</div>'
        for nazwa, pl, czas in bez
    )

    return f"""<!doctype html>
<html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ORDLY — projekt powiadomień push</title>
<style>{_STYL}</style></head>
<body><div class="strona">

<div class="eyebrow">Projekt do akceptacji · 22 września 2026</div>
<h1>Powiadomienia push <span>× Nokturn</span></h1>
<p class="lead">Jak powiadomienia na telefonie mają pasować do nowej aplikacji i nowej ikony.
Każdy dymek jest zbudowany z <b>prawdziwego kodu katalogu</b> — także w kolumnie „dziś”.
Zmiany istnieją już w kodzie, ale <b>nie są podpięte do wysyłki</b>: dopóki ich nie
zaakceptujesz, na telefon dalej idzie to, co widzisz po lewej.</p>

<div class="szczera"><b>Czego się NIE da:</b> dymek powiadomienia na iPhonie rysuje system —
materiał, krój SF, układ. Nie da się go zabarwić na teal ani zmienić kroju. „Pasowanie”
dzieje się więc tam, gdzie mamy wpływ: <b>ikona</b> (od teraz to Ordlak — i to on patrzy
z każdego powiadomienia), <b>słowa</b>, <b>liczba na ikonie</b>, <b>kiedy dzwoni, a kiedy
nie</b> i <b>dokąd prowadzi kliknięcie</b>.</div>

<section>
  <div class="eyebrow">01 · Liczba na ikonie</div>
  <h2>Plakietka = „Wymaga uwagi” z ekranu Start</h2>
  <p class="lead">Dziś każde powiadomienie ustawia plakietkę po swojemu: nowe zamówienie jej
  nie rusza, dyskusja wbija na sztywno <b>1</b> (kasując np. 4), przypomnienie o 9:00 liczy
  tylko paczki. Liczba na ikonie nie zgadza się z niczym, co widać po otwarciu. Po zmianie
  to zawsze ta sama suma co trzy kafle na ekranie Start.</p>
  <div class="ekrany">
    <div class="skala"><div class="telefon"><div class="ekran">
      <div class="dom">
        <div class="app"><i></i>Aparat</div><div class="app"><i></i>Zdjęcia</div>
        <div class="app"><i></i>Mapy</div><div class="app"><i></i>Pogoda</div>
        <div class="app"><div class="ordly"><img src="{ikona}" alt=""><b>{badge}</b></div>ORDLY</div>
        <div class="app"><i></i>Poczta</div><div class="app"><i></i>Safari</div>
        <div class="app"><i></i>Notatki</div>
      </div>
    </div></div></div>
    <div class="panel start">
      <div class="eyebrow">Ekran Start w aplikacji</div>
      <div class="kafle">
        <div class="kafel" style="--k:var(--coral)"><div class="l">Do spakowania</div><div class="v">3</div></div>
        <div class="kafel" style="--k:var(--teal)"><div class="l">Wartość dziś</div><div class="v">2340 zł</div></div>
        <div class="kafel" style="--k:#A79BFF"><div class="l">Dyskusje</div><div class="v">2</div></div>
        <div class="kafel" style="--k:var(--amber)"><div class="l">Zwroty</div><div class="v">1</div></div>
      </div>
      <p class="suma"><b>3 + 2 + 1 = {badge}</b> — ta sama liczba na ikonie. Wartość dnia do
      plakietki nie wchodzi: to informacja, nie rzecz do zrobienia.</p>
    </div>
  </div>
</section>

<section>
  <div class="eyebrow">02 · Ekran blokady</div>
  <h2>Jeden dzień z nowymi powiadomieniami</h2>
  <p class="lead">Dzwonią tylko te, które czegoś od Ciebie chcą — reszta przychodzi po cichu
  (wygaszona na makiecie). To ta sama zasada co w aplikacji: <b>blask to komunikat</b>.
  Rzeczy skończone nie świecą, więc i nie dzwonią.</p>
  <div class="ekrany">
    <div class="skala"><div class="telefon"><div class="ekran">
      <div class="zegar">16:14</div><div class="data">poniedziałek, 22 września</div>
      <div class="stos">{stos}</div>
    </div></div></div>
    <div class="panel">
      <table>
        <tr><th>Powiadomienie</th><th>Dźwięk</th><th>Dlaczego</th></tr>
        <tr><td>Nowe zamówienie</td><td>tak</td><td>trzeba spakować</td></tr>
        <tr><td>Nowa dyskusja, zwrot</td><td>tak</td><td>ktoś czeka na odpowiedź</td></tr>
        <tr><td>Wiadomość z OLX</td><td>tak</td><td>kupujący pyta</td></tr>
        <tr><td>Poranny raport</td><td>tak</td><td>raz dziennie, o tym, co czeka</td></tr>
        <tr><td>Awaria poczty / Allegro</td><td>tak</td><td>gubią się zamówienia</td></tr>
        <tr><td>Anulowanie</td><td>cicho</td><td>zamknięte — nic do zrobienia</td></tr>
        <tr><td>Lokalnie: doręczono</td><td>cicho <i>(nowe)</i></td><td>zamknięte — nic do zrobienia</td></tr>
        <tr><td>Hurtownia potwierdziła</td><td>cicho</td><td>informacja</td></tr>
      </table>
    </div>
  </div>
</section>

<section>
  <div class="eyebrow">03 · Zmiany</div>
  <h2>Dziś / po zmianie</h2>
  {sekcja_zmian}
</section>

<section>
  <div class="eyebrow">04 · Spójność z aplikacją</div>
  <h2>Co do czego pasuje</h2>
  <div class="panel"><table>
    <tr><th>Element</th><th>W aplikacji</th><th>W powiadomieniu</th></tr>
    <tr><td>Ordlak</td><td>maskotka pokazuje stan systemu</td>
        <td>jest ikoną każdego powiadomienia — nowa ikona aplikacji robi to sama</td></tr>
    <tr><td>„Wymaga uwagi”</td><td>kafle Do spakowania · Dyskusje · Zwroty</td>
        <td>ta sama suma na ikonie</td></tr>
    <tr><td>Noc</td><td>Ordlak zasypia o 22:00 i budzi się o <b>6:00</b></td>
        <td>cisza 22:00–<b>7:00</b> → wyrównuję Ordlaka do 7:00: gdy śpi, telefon nie dzwoni</td></tr>
    <tr><td>Słowa</td><td>„Do spakowania”, „Dyskusje”, „Zwroty”</td>
        <td>te same słowa w tytułach i w raporcie</td></tr>
    <tr><td>Kliknięcie</td><td>nowy pasek zakładek: Start · Zamówienia · Ordlak · Magazyn · Poczta</td>
        <td>każde prowadzi na istniejący ekran; raport — na Start (drobna zmiana w aplikacji:
        adres <code>/start</code>)</td></tr>
    <tr><td>Nazwy kanałów</td><td>etykieta „Lokalnie” (stałe 68/60 px)</td>
        <td>zostaje „AllegroLokalnie” — w treści jest miejsce, a to Twoja wcześniejsza decyzja</td></tr>
  </table></div>
</section>

<section>
  <div class="eyebrow">05 · Bez zmian</div>
  <h2>Reszta katalogu — już pasuje</h2>
  <p class="lead">Te powiadomienia zostają słowo w słowo. Po wdrożeniu nowej ikony wyglądają
  tak (ikona to jedyna różnica).</p>
  <div class="siatka" style="margin-top:20px">{reszta}</div>
</section>

<section>
  <div class="eyebrow">06 · Do decyzji</div>
  <h2>Co zatwierdzasz</h2>
  <div class="panel"><ol class="decyzje">
    <li><b>Plakietka</b> = suma Do spakowania + Dyskusje + Zwroty.</li>
    <li><b>Poranny raport</b> zamiast samego przypomnienia o pakowaniu (z poprawioną godziną), otwiera Start.</li>
    <li><b>Anulowanie</b> w katalogu, bez loginu, z kwotą — dalej ciche.</li>
    <li><b>Lokalnie „doręczono / anulowano”</b> — po cichu.</li>
    <li><b>Test powiadomień</b> z nowym tytułem.</li>
    <li><b>Ordlak śpi do 7:00</b>, tak jak trwa cisza powiadomień.</li>
  </ol>
  <p class="dlaczego">Możesz zatwierdzić wszystko albo wybrać numery. Poprawka godziny w pkt 2
  jest naprawą błędu, więc proponuję ją niezależnie od reszty.</p></div>
</section>

<footer>Plik wygenerowany przez <code>backend/scripts/generate_push_proposal.py</code> z prawdziwych
builderów <code>push_payload.py</code>. Obecny stan (bez propozycji) pokazuje
<code>podglad-powiadomien-push.html</code>.</footer>
</div></body></html>
"""


def main() -> None:
    _OUTPUT.write_text(build_html(), encoding="utf-8")
    print(f"Zapisano {_OUTPUT} ({_OUTPUT.stat().st_size / 1024:.0f} kB)")


if __name__ == "__main__":
    main()
