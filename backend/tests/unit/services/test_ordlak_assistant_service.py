"""
Testy asystenta Ordlaka - pętla narzędzi i treść raportów.

Klient Anthropic jest sobowtórem podstawianym przez `client_factory`,
więc żaden test nie wychodzi do sieci ani nie potrzebuje klucza API.
Sprawdzamy dwie rzeczy naraz: że pętla rozmowy odsyła modelowi wyniki
narzędzi we właściwym kształcie, i że same narzędzia liczą to, co trzeba
(np. "wczoraj" nie zawiera dzisiejszej sprzedaży).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from pydantic import SecretStr

from app.core.config import MailWatchSettings, OrdlakSettings
from app.domain.entities.customer import Customer
from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.issue import Issue, IssueMessage
from app.domain.entities.mail_message import MailMessage
from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.entities.product import Product
from app.services.dashboard_service import DashboardService
from app.services.inventory_service import InventoryService
from app.services.issues_service import IssuesService
from app.services.mailbox_service import MailboxService
from app.services.ordlak_assistant_service import (
    MAX_HISTORY_TURNS,
    MAX_TOOL_ROUNDS,
    ChatTurn,
    OrdlakAssistantService,
    OrdlakConversationNotFoundError,
    OrdlakError,
    OrdlakNotConfiguredError,
    calculate_price,
)
from app.services.returns_service import ReturnsService
from app.services.search_service import SearchService
from app.utils.time import utc_now
from tests.fakes.fake_anthropic import (
    FakeAnthropic,
    FakeResponse,
    StubHealthService,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
)
from tests.fakes.fake_inventory_repository import FakeInventoryRepository
from tests.fakes.fake_mail_repository import FakeMailRepository
from tests.fakes.fake_marketplace_plugin import FakeMarketplacePlugin
from tests.fakes.fake_order_repository import FakeOrderRepository
from tests.fakes.fake_ordlak_conversation_repository import (
    FakeOrdlakConversationRepository,
)
from tests.fakes.fake_return_repository import FakeReturnRepository

# ----------------------------------------------------------------------
# Budowanie serwisu
# ----------------------------------------------------------------------


def _settings(configured: bool = True) -> OrdlakSettings:
    return OrdlakSettings(
        _env_file=None,
        ANTHROPIC_API_KEY=SecretStr("sk-test" if configured else ""),
        ANTHROPIC_MODEL="claude-sonnet-5",
    )


@dataclass
class Harness:
    """Serwis razem z magazynem danych, żeby testy mogły je wypełniać."""

    service: OrdlakAssistantService
    client: FakeAnthropic
    orders: FakeOrderRepository
    inventory: FakeInventoryRepository
    returns: FakeReturnRepository
    plugin: FakeMarketplacePlugin
    mail: FakeMailRepository
    conversations: FakeOrdlakConversationRepository


def _build(
    client: FakeAnthropic | None = None,
    configured: bool = True,
    imap_configured: bool = True,
) -> Harness:
    anthropic = client or FakeAnthropic()
    orders = FakeOrderRepository()
    inventory = FakeInventoryRepository()
    returns = FakeReturnRepository()
    plugin = FakeMarketplacePlugin()
    mail = FakeMailRepository()
    conversations = FakeOrdlakConversationRepository()
    # `_env_file=None` jest konieczne: bez tego pydantic-settings wciąga
    # prawdziwy `.env` dewelopera i "skrzynka wyłączona" przestaje być
    # wyłączona (patrz pułapka w project-ordly-deployment).
    mail_settings = MailWatchSettings(
        _env_file=None,
        IMAP_USER="sklep@example.com" if imap_configured else "",
        IMAP_PASS=SecretStr("tajne" if imap_configured else ""),
    )
    settings = _settings(configured)
    service = OrdlakAssistantService(
        settings=settings,
        order_repository=orders,
        inventory_service=InventoryService(inventory),
        returns_service=ReturnsService(returns),
        dashboard_service=DashboardService(orders, inventory),
        health_service=StubHealthService(),  # type: ignore[arg-type]
        search_service=SearchService(orders),
        issues_service=IssuesService(plugin),
        mailbox_service=MailboxService(mail, mail_settings, watcher_factory=lambda: None),
        conversation_repository=conversations,
        # Brak klucza = brak fabryki, więc serwis idzie ścieżką
        # "nie skonfigurowano" dokładnie jak na prawdziwym Pi.
        client_factory=(lambda: anthropic) if configured else None,
    )
    return Harness(
        service, anthropic, orders, inventory, returns, plugin, mail, conversations
    )


def _order(
    external_id: str,
    when: datetime,
    amount: str = "100.00",
    marketplace: str = "allegro",
    product: str = "Kubek ceramiczny",
    quantity: int = 1,
    fulfillment_status: str | None = None,
) -> Order:
    return Order(
        external_id=external_id,
        marketplace=marketplace,
        buyer=Customer(login="jan_kowalski", email="jan@example.com"),
        products=[
            Product(
                external_id=f"P-{external_id}",
                name=product,
                quantity=quantity,
                unit_price=Decimal(amount) / quantity,
            )
        ],
        total_amount=Decimal(amount),
        currency="PLN",
        status="NEW",
        order_date=when,
        fulfillment_status=fulfillment_status,
    )


def _item(sku: str, name: str, stock: int, min_stock: int = 0) -> InventoryItem:
    return InventoryItem(sku=sku, name=name, stock=stock, min_stock=min_stock)


async def _ask(harness: Harness, question: str = "Jak leci?") -> Any:
    return await harness.service.answer([ChatTurn(role="user", content=question)])


def _tool_results(call: dict[str, Any]) -> list[str]:
    """Wyciąga treści `tool_result` z wiadomości wysłanej do modelu."""
    results: list[str] = []
    for message in call["messages"]:
        content = message["content"]
        if not isinstance(content, list):
            continue
        results.extend(
            str(block["content"]) for block in content if block.get("type") == "tool_result"
        )
    return results


# ----------------------------------------------------------------------
# Pętla rozmowy
# ----------------------------------------------------------------------


class TestPetlaRozmowy:
    async def test_odpowiedz_bez_narzedzi_wraca_wprost(self):
        harness = _build(FakeAnthropic([FakeResponse([TextBlock("Cześć, w czym pomóc?")])]))

        answer = await _ask(harness)

        assert answer.reply == "Cześć, w czym pomóc?"
        assert answer.used_tools == ()
        assert len(harness.client.calls) == 1

    async def test_wynik_narzedzia_wraca_do_modelu_i_konczy_sie_odpowiedzia(self):
        harness = _build(
            FakeAnthropic(
                [
                    FakeResponse([ToolUseBlock("niskie_stany")], stop_reason="tool_use"),
                    FakeResponse([TextBlock("Brakuje butelek.")]),
                ]
            )
        )
        harness.inventory.items["PET30"] = _item("PET30", "Butelka PET 30ml", 2, min_stock=10)

        answer = await _ask(harness, "Co ma niski stan?")

        assert answer.reply == "Brakuje butelek."
        assert answer.used_tools == ("niskie_stany",)
        assert "Butelka PET 30ml" in _tool_results(harness.client.calls[1])[0]

    async def test_kilka_narzedzi_w_jednej_turze_daje_kilka_wynikow(self):
        harness = _build(
            FakeAnthropic(
                [
                    FakeResponse(
                        [
                            ToolUseBlock("niskie_stany", id="t1"),
                            ToolUseBlock("stan_systemu", id="t2"),
                        ],
                        stop_reason="tool_use",
                    ),
                    FakeResponse([TextBlock("Wszystko sprawdzone.")]),
                ]
            )
        )

        answer = await _ask(harness)

        assert answer.used_tools == ("niskie_stany", "stan_systemu")
        assert len(_tool_results(harness.client.calls[1])) == 2

    async def test_bloki_myslenia_wracaja_do_modelu_z_podpisem(self):
        """
        Model z włączonym myśleniem odrzuca turę z `tool_use`, w której
        zabrakło bloku `thinking` - musi wrócić w całości, z podpisem.
        """
        harness = _build(
            FakeAnthropic(
                [
                    FakeResponse(
                        [
                            ThinkingBlock("Sprawdzę magazyn.", signature="sig-abc"),
                            ToolUseBlock("niskie_stany"),
                        ],
                        stop_reason="tool_use",
                    ),
                    FakeResponse([TextBlock("Gotowe.")]),
                ]
            )
        )

        await _ask(harness)

        assistant_turn = harness.client.calls[1]["messages"][1]
        thinking = next(b for b in assistant_turn["content"] if b["type"] == "thinking")
        assert thinking["thinking"] == "Sprawdzę magazyn."
        assert thinking["signature"] == "sig-abc"

    async def test_historia_rozmowy_leci_do_modelu_w_calosci(self):
        harness = _build()

        await harness.service.answer(
            [
                ChatTurn(role="user", content="Ile sprzedałem?"),
                ChatTurn(role="assistant", content="Dwa zamówienia."),
                ChatTurn(role="user", content="A wczoraj?"),
            ]
        )

        messages = harness.client.calls[0]["messages"]
        assert [m["role"] for m in messages] == ["user", "assistant", "user"]
        assert messages[-1]["content"] == "A wczoraj?"

    async def test_dzisiejsza_data_trafia_do_system_promptu(self):
        """Model nie zna dzisiejszej daty - bez niej kalendarz nic nie znaczy."""
        harness = _build()

        await _ask(harness)

        assert utc_now().date().isoformat() in harness.client.calls[0]["system"]

    async def test_brak_klucza_api_zglasza_brak_konfiguracji(self):
        harness = _build(configured=False)

        with pytest.raises(OrdlakNotConfiguredError, match="ANTHROPIC_API_KEY"):
            await _ask(harness)

    async def test_pusta_rozmowa_jest_bledem(self):
        harness = _build()

        with pytest.raises(OrdlakError, match="Pusta rozmowa"):
            await harness.service.answer([])

    async def test_blad_api_ma_czytelny_komunikat_po_polsku(self):
        error = Exception("boom")
        error.status_code = 401  # type: ignore[attr-defined]
        harness = _build(FakeAnthropic(raise_error=error))

        with pytest.raises(OrdlakError, match="401"):
            await _ask(harness)

    async def test_model_ktory_w_kolko_pyta_o_dane_konczy_sie_bledem(self):
        harness = _build(
            FakeAnthropic([FakeResponse([ToolUseBlock("niskie_stany")], stop_reason="tool_use")])
        )

        with pytest.raises(OrdlakError, match="podejściach"):
            await _ask(harness)

        assert len(harness.client.calls) == MAX_TOOL_ROUNDS

    async def test_nieznane_narzedzie_nie_wywraca_czatu(self):
        harness = _build(
            FakeAnthropic(
                [
                    FakeResponse([ToolUseBlock("wymyslone")], stop_reason="tool_use"),
                    FakeResponse([TextBlock("Nie umiem tego sprawdzić.")]),
                ]
            )
        )

        answer = await _ask(harness)

        assert answer.reply == "Nie umiem tego sprawdzić."
        assert "nie istnieje" in _tool_results(harness.client.calls[1])[0]

    async def test_pusta_odpowiedz_na_limicie_dlugosci_mowi_o_tym_wprost(self):
        harness = _build(FakeAnthropic([FakeResponse([], stop_reason="max_tokens")]))

        with pytest.raises(OrdlakError, match="ucięta"):
            await _ask(harness)


# ----------------------------------------------------------------------
# Narzędzia
# ----------------------------------------------------------------------


def _with_tool(name: str, payload: dict[str, Any] | None = None) -> FakeAnthropic:
    return FakeAnthropic(
        [
            FakeResponse([ToolUseBlock(name, input=payload or {})], stop_reason="tool_use"),
            FakeResponse([TextBlock("Gotowe.")]),
        ]
    )


async def _run_tool(harness: Harness) -> str:
    await _ask(harness)
    return _tool_results(harness.client.calls[1])[0]


class TestPodsumowanieSprzedazy:
    async def test_wczoraj_nie_zawiera_dzisiejszej_sprzedazy(self):
        """
        Repozytorium umie liczyć tylko "od daty", więc zamknięty przedział
        powstaje przez odjęcie dzisiejszego ogona. To najłatwiejsze miejsce
        na pomyłkę w całym module - i najbardziej mylące dla użytkownika.
        """
        harness = _build(_with_tool("podsumowanie_sprzedazy", {"okres": "wczoraj"}))
        now = utc_now()
        today_start = datetime(now.year, now.month, now.day)
        await harness.orders.save(
            _order("WCZORAJ-1", today_start - timedelta(hours=5), amount="40.00")
        )
        await harness.orders.save(_order("DZIS-1", today_start + timedelta(hours=1), "900.00"))

        result = await _run_tool(harness)

        assert "Zamowienia: 1" in result
        assert "40.0 zl" in result
        assert "900" not in result

    async def test_liczy_sztuki_i_wartosc_najlepiej_sprzedajacych_sie(self):
        harness = _build(_with_tool("podsumowanie_sprzedazy", {"okres": "7dni"}))
        now = utc_now()
        await harness.orders.save(_order("A", now, "60.00", product="Butelka", quantity=3))
        await harness.orders.save(_order("B", now, "20.00", product="Butelka", quantity=1))
        await harness.orders.save(_order("C", now, "10.00", product="Kroplomierz"))

        result = await _run_tool(harness)

        assert "Butelka: 4 szt., 80.0 zl" in result
        assert "Kroplomierz: 1 szt." in result

    async def test_rozbija_sprzedaz_na_kanaly(self):
        harness = _build(_with_tool("podsumowanie_sprzedazy", {"okres": "30dni"}))
        now = utc_now()
        await harness.orders.save(_order("A", now, marketplace="allegro"))
        await harness.orders.save(_order("B", now, marketplace="allegro"))
        await harness.orders.save(_order("C", now, marketplace="olx"))

        result = await _run_tool(harness)

        assert "allegro: 2" in result
        assert "olx: 1" in result

    async def test_brak_sprzedazy_mowi_wprost_zamiast_zerowac_liste(self):
        harness = _build(_with_tool("podsumowanie_sprzedazy", {"okres": "dzis"}))

        result = await _run_tool(harness)

        assert "Zamowienia: 0" in result
        assert "Brak sprzedanych pozycji" in result


class TestMagazyn:
    async def test_szuka_po_nazwie_i_po_sku(self):
        harness = _build(_with_tool("magazyn", {"szukaj": "pet30"}))
        harness.inventory.items["PET30"] = _item("PET30", "Butelka PET 30ml", 5)
        harness.inventory.items["KROPL"] = _item("KROPL", "Kroplomierz", 40)

        result = await _run_tool(harness)

        assert "Butelka PET 30ml" in result
        assert "Kroplomierz" not in result

    async def test_brak_dopasowania_mowi_czego_szukano(self):
        harness = _build(_with_tool("magazyn", {"szukaj": "rower"}))
        harness.inventory.items["PET30"] = _item("PET30", "Butelka PET 30ml", 5)

        result = await _run_tool(harness)

        assert "rower" in result

    async def test_dluga_lista_jest_ucinana_z_informacja_ile_zostalo(self):
        harness = _build(_with_tool("magazyn", {"limit": 2}))
        for index in range(5):
            harness.inventory.items[f"SKU{index}"] = _item(f"SKU{index}", f"Produkt {index}", 1)

        result = await _run_tool(harness)

        assert "oraz 3 dalszych pozycji" in result

    async def test_limit_spoza_zakresu_schodzi_do_wartosci_granicznej(self):
        """Model bywa hojny z liczbami - 5000 pozycji nie ma trafić do promptu."""
        harness = _build(_with_tool("magazyn", {"limit": 5000}))
        for index in range(70):
            harness.inventory.items[f"SKU{index}"] = _item(f"SKU{index}", f"Produkt {index}", 1)

        result = await _run_tool(harness)

        assert "oraz 10 dalszych pozycji" in result


class TestNiskieStany:
    async def test_zaznacza_pozycje_ponizej_progu(self):
        harness = _build(_with_tool("niskie_stany"))
        harness.inventory.items["PET30"] = _item("PET30", "Butelka PET 30ml", 2, min_stock=10)

        result = await _run_tool(harness)

        assert "PONIZEJ PROGU" in result
        assert "prog 10" in result

    async def test_pelny_magazyn_mowi_ze_nie_ma_brakow(self):
        harness = _build(_with_tool("niskie_stany"))
        harness.inventory.items["PET30"] = _item("PET30", "Butelka PET 30ml", 99, min_stock=10)

        result = await _run_tool(harness)

        assert "Zadna pozycja nie jest ponizej progu" in result


class TestZamowieniaIZwroty:
    async def test_filtr_niewyslanych_pomija_wyslane(self):
        harness = _build(_with_tool("ostatnie_zamowienia", {"tylko_niewyslane": True}))
        now = utc_now()
        await harness.orders.save(_order("CZEKA", now, fulfillment_status="NEW"))
        await harness.orders.save(_order("POSZLO", now, fulfillment_status="SENT"))

        result = await _run_tool(harness)

        assert "CZEKA" in result
        assert "POSZLO" not in result

    async def test_zwroty_pokazuja_zamowienie_zrodlowe(self, sample_return: OrderReturn):
        harness = _build(_with_tool("zwroty"))
        await harness.returns.save(sample_return)

        result = await _run_tool(harness)

        assert "RETURN-001" in result
        assert "ORDER-001" in result

    async def test_brak_zwrotow_to_normalna_odpowiedz(self):
        harness = _build(_with_tool("zwroty"))

        assert "Brak zwrotow" in await _run_tool(harness)


class TestKalendarzISystem:
    async def test_kalendarz_podaje_date_i_ile_dni_zostalo(self):
        harness = _build(_with_tool("kalendarz_sprzedazowy", {"dni_do_przodu": 365}))

        result = await _run_tool(harness)

        assert "Horyzont: 365 dni" in result
        assert "za " in result

    async def test_stan_systemu_laczy_zdrowie_i_dzisiejsze_liczby(self):
        harness = _build(_with_tool("stan_systemu"))
        await harness.orders.save(_order("DZIS", utc_now(), "150.00", fulfillment_status="NEW"))
        harness.inventory.items["PET30"] = _item("PET30", "Butelka PET 30ml", 1, min_stock=10)

        result = await _run_tool(harness)

        assert "5 minut temu" in result
        assert "Zamowienia dzis: 1" in result
        assert "Czeka na wysylke: 1" in result
        assert "Ponizej progu w magazynie: 1" in result


# ----------------------------------------------------------------------
# Kalkulator ceny
# ----------------------------------------------------------------------


class TestKalkulatorCeny:
    """
    Cena to jedyna liczba, której nie ma w żadnej tabeli - liczy ją
    Python, nigdy model. Wzór musi być powtarzalny co do grosza.
    """

    def test_prowizja_liczy_sie_tez_od_wysylki_do_kupujacego(self):
        """
        Nieoczywista reguła Allegro: podstawą prowizji jest cena PLUS
        koszt wysyłki zapłacony przez kupującego. Te same liczby dawał
        generator ofert przed jego usunięciem.
        """
        breakdown = calculate_price(
            purchase_cost=25.0,
            commission_percent=10.0,
            target_margin_percent=30.0,
            inbound_shipping_cost=8.0,
            buyer_shipping_cost=12.0,
        )

        assert breakdown.suggested_price == 57.0
        assert breakdown.commission_amount == 6.9
        assert breakdown.margin_amount == 17.1

    def test_rozbicie_sie_domyka(self):
        """Zakup + sprowadzenie + prowizja + marża musi dać cenę."""
        breakdown = calculate_price(
            purchase_cost=25.0,
            commission_percent=10.0,
            target_margin_percent=30.0,
            inbound_shipping_cost=8.0,
            buyer_shipping_cost=12.0,
        )
        suma = (
            breakdown.purchase_cost
            + breakdown.inbound_shipping_cost
            + breakdown.commission_amount
            + breakdown.margin_amount
        )

        assert round(suma, 2) == breakdown.suggested_price

    def test_koszty_transportu_sa_opcjonalne(self):
        breakdown = calculate_price(
            purchase_cost=50.0, commission_percent=10.0, target_margin_percent=40.0
        )

        assert breakdown.suggested_price == 100.0
        assert breakdown.commission_amount == 10.0

    def test_prowizja_i_marza_ponad_100_procent_sa_bledem(self):
        with pytest.raises(OrdlakError, match="100%"):
            calculate_price(
                purchase_cost=10.0, commission_percent=70.0, target_margin_percent=40.0
            )

    def test_ujemna_kwota_jest_bledem(self):
        with pytest.raises(OrdlakError, match="Koszt zakupu"):
            calculate_price(
                purchase_cost=-1.0, commission_percent=10.0, target_margin_percent=30.0
            )

    async def test_narzedzie_oddaje_cene_i_rozbicie(self):
        harness = _build(
            _with_tool(
                "kalkulator_ceny",
                {
                    "koszt_zakupu": 25,
                    "prowizja_procent": 10,
                    "marza_procent": 30,
                    "koszt_sprowadzenia": 8,
                    "koszt_wysylki_do_kupujacego": 12,
                },
            )
        )

        result = await _run_tool(harness)

        assert "Cena sugerowana: 57.0 zl" in result
        assert "6.9 zl" in result

    async def test_narzedzie_oddaje_blad_modelowi_zamiast_wywracac_czat(self):
        harness = _build(
            _with_tool(
                "kalkulator_ceny",
                {"koszt_zakupu": 10, "prowizja_procent": 70, "marza_procent": 40},
            )
        )

        result = await _run_tool(harness)

        assert result.startswith("BLAD:")
        assert "100%" in result


# ----------------------------------------------------------------------
# Szukanie, dyskusje, poczta
# ----------------------------------------------------------------------


class TestSzukanie:
    async def test_znajduje_po_loginie_kupujacego(self):
        harness = _build(_with_tool("szukaj", {"fraza": "jan_kowalski"}))
        await harness.orders.save(_order("A-1", utc_now(), "60.00"))
        await harness.orders.save(_order("A-2", utc_now(), "40.00"))

        result = await _run_tool(harness)

        assert "Znaleziono 2 zamowien" in result
        assert "100.0 zl" in result

    async def test_brak_wynikow_mowi_czego_szukano(self):
        harness = _build(_with_tool("szukaj", {"fraza": "nieistniejacy"}))

        assert "nieistniejacy" in await _run_tool(harness)

    async def test_pusta_fraza_to_blad_a_nie_cala_baza(self):
        harness = _build(_with_tool("szukaj", {"fraza": "   "}))

        assert (await _run_tool(harness)).startswith("BLAD:")


class TestDyskusje:
    async def test_lista_pokazuje_status_i_zamowienie(self):
        harness = _build(_with_tool("dyskusje"))
        harness.plugin.issues_to_return = [
            Issue(
                external_id="ISSUE-1",
                marketplace="allegro",
                type="DISPUTE",
                status="ONGOING",
                order_external_id="ORDER-7",
                buyer_login="jan_kowalski",
                subject="Uszkodzona przesyłka",
                description=None,
                opened_at=datetime(2026, 9, 1, 10, 0),
                messages_count=3,
                chat_active=True,
                last_message_at=datetime(2026, 9, 2, 8, 0),
            )
        ]

        result = await _run_tool(harness)

        assert "ISSUE-1" in result
        assert "ORDER-7" in result
        assert "Uszkodzona przesyłka" in result

    async def test_watek_wraca_w_kolejnosci_od_najstarszej(self):
        harness = _build(_with_tool("watek_dyskusji", {"id_dyskusji": "ISSUE-1"}))
        harness.plugin.issue_messages_to_return = [
            IssueMessage(
                id="M2",
                text="Druga wiadomosc",
                author_login="sprzedawca",
                author_role="SELLER",
                created_at=datetime(2026, 9, 2, 9, 0),
            ),
            IssueMessage(
                id="M1",
                text="Pierwsza wiadomosc",
                author_login="jan_kowalski",
                author_role="BUYER",
                created_at=datetime(2026, 9, 1, 9, 0),
            ),
        ]

        result = await _run_tool(harness)

        assert result.index("Pierwsza wiadomosc") < result.index("Druga wiadomosc")

    async def test_pusty_numer_dyskusji_to_blad(self):
        harness = _build(_with_tool("watek_dyskusji", {"id_dyskusji": ""}))

        assert (await _run_tool(harness)).startswith("BLAD:")

    async def test_niedostepne_allegro_wraca_do_modelu_jako_komunikat(self):
        harness = _build(_with_tool("dyskusje"))
        harness.plugin.should_raise_issues_api_error = True

        result = await _run_tool(harness)

        assert result.startswith("BLAD odczytu danych (dyskusje)")


class TestPoczta:
    async def test_wylaczony_imap_mowi_o_konfiguracji_a_nie_o_pustce(self):
        """
        Pusta lista musi umieć powiedzieć DLACZEGO - inaczej model
        stwierdzi "nie masz maili", gdy naprawdę skrzynka jest wyłączona.
        """
        harness = _build(_with_tool("poczta"), imap_configured=False)

        result = await _run_tool(harness)

        assert "nie jest skonfigurowana" in result

    async def test_pokazuje_nadawce_temat_i_stan_przeczytania(self):
        harness = _build(_with_tool("poczta"))
        await harness.mail.save(
            MailMessage(
                message_id="<a@x>",
                sender="noreply@allegromail.pl",
                subject="Masz nowe zamówienie",
                received_at=datetime(2026, 9, 5, 12, 0),
                source="allegro",
                body_preview="Kupujący zapłacił",
                is_read=False,
            )
        )

        result = await _run_tool(harness)

        assert "NIEPRZECZYTANY" in result
        assert "Masz nowe zamówienie" in result
        assert "Kupujący zapłacił" in result

    async def test_pusta_skrzynka_przy_dzialajacym_imap_podaje_licznik(self):
        harness = _build(_with_tool("poczta", {"tylko_nieprzeczytane": True}))

        result = await _run_tool(harness)

        assert "Brak maili" in result
        assert "tylko nieprzeczytane" in result


# ----------------------------------------------------------------------
# Zapisywanie rozmów
# ----------------------------------------------------------------------


class TestZapisRozmowy:
    async def test_pierwsze_pytanie_zaklada_watek_z_tytulem_z_pytania(self):
        harness = _build(FakeAnthropic([FakeResponse([TextBlock("Trzy zamówienia.")])]))

        result = await harness.service.ask("Ile sprzedałem w tym tygodniu?")

        conversation = harness.conversations.conversations[result.conversation_id]
        assert conversation.title == "Ile sprzedałem w tym tygodniu?"
        assert [m.role for m in conversation.messages] == ["user", "assistant"]
        assert conversation.messages[1].content == "Trzy zamówienia."

    async def test_dlugie_pytanie_daje_przyciety_tytul(self):
        harness = _build()

        result = await harness.service.ask("Ile " + "bardzo " * 30 + "sprzedałem?")

        title = harness.conversations.conversations[result.conversation_id].title
        assert len(title) <= 60
        assert title.endswith("…")

    async def test_slad_po_narzedziach_zostaje_przy_odpowiedzi(self):
        """
        `used_tools` zapisujemy razem z treścią, a nie liczymy na nowo -
        wracając do wątku sprzed tygodnia trzeba widzieć narzędzia, które
        wtedy dały te liczby.
        """
        harness = _build(_with_tool("niskie_stany"))

        result = await harness.service.ask("Co ma niski stan?")

        odpowiedz = harness.conversations.conversations[result.conversation_id].messages[1]
        assert odpowiedz.used_tools == ("niskie_stany",)

    async def test_kolejne_pytanie_dokleja_sie_do_tego_samego_watku(self):
        harness = _build()

        first = await harness.service.ask("Ile sprzedałem?")
        second = await harness.service.ask("A wczoraj?", conversation_id=first.conversation_id)

        assert second.conversation_id == first.conversation_id
        conversation = harness.conversations.conversations[first.conversation_id]
        assert len(conversation.messages) == 4

    async def test_model_dostaje_wczesniejsza_historie_watku(self):
        harness = _build()

        first = await harness.service.ask("Ile sprzedałem?")
        harness.client.calls.clear()
        await harness.service.ask("A wczoraj?", conversation_id=first.conversation_id)

        wyslane = harness.client.calls[0]["messages"]
        assert [m["role"] for m in wyslane] == ["user", "assistant", "user"]
        assert wyslane[-1]["content"] == "A wczoraj?"

    async def test_historia_jest_przycinana_do_ostatnich_wypowiedzi(self):
        """Bardzo długi wątek nie może kosztować przy każdej odpowiedzi."""
        harness = _build()
        conversation = await harness.conversations.create("Stara rozmowa")
        assert conversation.id is not None
        for index in range(MAX_HISTORY_TURNS + 10):
            await harness.conversations.append(
                conversation.id, "user" if index % 2 == 0 else "assistant", f"tekst {index}"
            )
        harness.client.calls.clear()

        await harness.service.ask("Nowe pytanie", conversation_id=conversation.id)

        wyslane = harness.client.calls[0]["messages"]
        assert len(wyslane) == MAX_HISTORY_TURNS + 1

    async def test_pytanie_zapisuje_sie_nawet_gdy_model_padnie(self):
        """
        Po błędzie sieci użytkownik ma wrócić do wątku i zobaczyć, o co
        pytał - inaczej nie wie, czy pytanie w ogóle wyszło.
        """
        blad = Exception("boom")
        blad.status_code = 500  # type: ignore[attr-defined]
        harness = _build(FakeAnthropic(raise_error=blad))

        with pytest.raises(OrdlakError):
            await harness.service.ask("Ile sprzedałem?")

        conversation = harness.conversations.conversations[1]
        assert [m.content for m in conversation.messages] == ["Ile sprzedałem?"]

    async def test_nieistniejacy_watek_to_osobny_blad(self):
        harness = _build()

        with pytest.raises(OrdlakConversationNotFoundError, match="999"):
            await harness.service.ask("Ile sprzedałem?", conversation_id=999)

    async def test_puste_pytanie_nie_zaklada_watku(self):
        harness = _build()

        with pytest.raises(OrdlakError, match="Puste pytanie"):
            await harness.service.ask("   ")

        assert harness.conversations.conversations == {}

    async def test_lista_rozmow_ma_ostatnio_uzywana_na_gorze(self):
        harness = _build()
        first = await harness.service.ask("Pierwsze pytanie")
        second = await harness.service.ask("Drugie pytanie")
        await harness.service.ask("Dopisek", conversation_id=first.conversation_id)

        lista = await harness.service.conversations()

        assert [c.id for c in lista] == [first.conversation_id, second.conversation_id]

    async def test_usuniecie_watku_zwraca_czy_bylo_co_usuwac(self):
        harness = _build()
        result = await harness.service.ask("Pytanie")

        assert await harness.service.delete_conversation(result.conversation_id) is True
        assert await harness.service.delete_conversation(result.conversation_id) is False
        assert await harness.service.conversation(result.conversation_id) is None
