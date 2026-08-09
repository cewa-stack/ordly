"""
Testy OrdlakService - walidacja wejścia, prompt, obsługa odpowiedzi modelu.

Klient Anthropic jest podmieniany fake'iem przez `client_factory`, więc
żaden test nie wychodzi do sieci ani nie potrzebuje klucza API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import SecretStr

from app.core.config import OrdlakSettings
from app.services.ordlak_service import (
    OrdlakError,
    OrdlakNotConfiguredError,
    OrdlakPhoto,
    OrdlakService,
    validate_title,
)
from tests.fakes.fake_ordlak_repository import FakeOrdlakRepository

# 70 znaków - powyżej celu 65, więc nie wywołuje ponowienia.
DOBRY_TYTUL = "Kubek ceramiczny biały 350 ml porcelana matowa do kawy herbaty prezent"
KROTKI_TYTUL = "Kubek ceramiczny biały"

# Opis musi przekroczyć DESCRIPTION_TARGET_LENGTH, inaczej serwis słusznie
# uzna go za szkielet i ponowi zapytanie - dopisek `x` dobija długość bez
# zaciemniania czytelnej treści.
DOBRY_OPIS = (
    "<p><strong>⭐ Kubek ceramiczny biały 350 ml ⭐</strong></p>"
    "<p>Wysokiej jakości <strong>kubek ceramiczny</strong> o pojemności 350 ml.</p>"
    "<p><strong>Najważniejsze cechy produktu:</strong></p>"
    "<ul><li><strong>Pojemność 350 ml:</strong> na dużą kawę lub herbatę.</li>"
    "<li><strong>Materiał ceramika:</strong> długo utrzymuje temperaturę.</li></ul>"
    "<p><strong>Wszechstronne zastosowanie:</strong></p>"
    "<ul><li>✅ Kawa i herbata</li><li>✅ Prezent</li></ul>"
    "<p><strong>Specyfikacja techniczna:</strong></p>"
    "<ul><li><strong>Pojemność:</strong> 350 ml</li>"
    "<li><strong>Materiał:</strong> ceramika</li></ul>"
    "<p>Stan produktu: nowy, nieużywany.</p>"
) + "<p>x</p>" * 120
KROTKI_OPIS = "<p>Kubek ceramiczny o pojemności 350 ml.</p>"

# Alias używany tam, gdzie treść opisu nie ma znaczenia dla testu.
OPIS = DOBRY_OPIS


@dataclass
class _FakeBlock:
    type: str
    input: dict[str, Any] | None = None


@dataclass
class _FakeResponse:
    content: list[_FakeBlock]
    stop_reason: str = "tool_use"


class _FakeMessages:
    def __init__(self, owner: _FakeAnthropic) -> None:
        self._owner = owner

    async def create(self, **kwargs: Any) -> _FakeResponse:
        self._owner.calls.append(kwargs)
        if self._owner.raise_error is not None:
            raise self._owner.raise_error
        index = min(len(self._owner.calls) - 1, len(self._owner.responses) - 1)
        return self._owner.responses[index]


class _FakeAnthropic:
    """Minimalny sobowtór `AsyncAnthropic` - tylko `messages.create`."""

    def __init__(
        self,
        responses: list[_FakeResponse] | None = None,
        raise_error: Exception | None = None,
    ) -> None:
        self.responses = responses or [_ok_response()]
        self.raise_error = raise_error
        self.calls: list[dict[str, Any]] = []
        self.messages = _FakeMessages(self)


def _ok_response(
    title: str = DOBRY_TYTUL,
    notes: str = "Bez widocznych rys.",
    description: str = DOBRY_OPIS,
) -> _FakeResponse:
    return _FakeResponse(
        content=[
            _FakeBlock(
                type="tool_use",
                input={
                    "title": title,
                    "description_html": description,
                    "condition_notes": notes,
                },
            )
        ]
    )


def _settings(max_photo_size_mb: int = 5) -> OrdlakSettings:
    return OrdlakSettings(
        _env_file=None,
        ANTHROPIC_API_KEY=SecretStr("sk-test"),
        ANTHROPIC_MODEL="claude-sonnet-5",
        ORDLAK_MAX_PHOTO_SIZE_MB=max_photo_size_mb,
    )


def _service(
    client: _FakeAnthropic | None = None,
    repository: FakeOrdlakRepository | None = None,
    max_photo_size_mb: int = 5,
) -> tuple[OrdlakService, _FakeAnthropic, FakeOrdlakRepository]:
    fake_client = client or _FakeAnthropic()
    repo = repository or FakeOrdlakRepository()
    service = OrdlakService(
        repository=repo,
        settings=_settings(max_photo_size_mb),
        client_factory=lambda: fake_client,
    )
    return service, fake_client, repo


async def _generate(service: OrdlakService, **overrides: Any):
    payload: dict[str, Any] = {
        "note": "Biały kubek ceramiczny 350 ml, kupiony w hurtowni",
        "condition": "new",
        "purchase_cost": 25.0,
        "inbound_shipping_cost": 8.0,
        "buyer_shipping_cost": 12.0,
        "commission_percent": 10.0,
        "target_margin_percent": 30.0,
    }
    payload.update(overrides)
    return await service.generate(**payload)


class TestValidateTitle:
    def test_akceptuje_tytul_w_limicie(self):
        validate_title(DOBRY_TYTUL)

    def test_odrzuca_ponizej_12_znakow(self):
        with pytest.raises(OrdlakError, match="12-75"):
            validate_title("Kubek biały")

    def test_odrzuca_powyzej_75_znakow(self):
        with pytest.raises(OrdlakError, match="12-75"):
            validate_title("x" * 76)

    def test_odrzuca_mniej_niz_trzy_slowa(self):
        with pytest.raises(OrdlakError, match="3 słowa"):
            validate_title("Kubekceramiczny bialy")


class TestGenerate:
    async def test_zwraca_tytul_opis_i_cene(self):
        service, _, _ = _service()

        draft = await _generate(service)

        assert draft.generation.generated_title == DOBRY_TYTUL
        assert draft.generation.generated_description_html == OPIS
        assert draft.price_breakdown.suggested_price == 57.0
        assert draft.price_breakdown.commission_amount == 6.9

    async def test_zapisuje_generacje_w_historii(self):
        service, _, repo = _service()

        draft = await _generate(service)

        assert draft.generation.id is not None
        assert await repo.get_by_id(draft.generation.id) is not None

    async def test_cena_nie_pochodzi_z_modelu(self):
        """
        Nawet gdy model wpisze cenę w tytuł, backend liczy swoją.

        To jest świadoma decyzja z sekcji 6 - kalkulacja ma być
        audytowalna, nie zgadywana przez LLM.
        """
        client = _FakeAnthropic(
            responses=[
                _ok_response(title="Kubek ceramiczny biały 350ml cena 999 zl okazyjnie")
            ]
        )
        service, _, _ = _service(client)

        draft = await _generate(service)

        assert draft.price_breakdown.suggested_price == 57.0

    async def test_wysyla_zdjecia_jako_bloki_obrazu(self):
        service, client, _ = _service()

        await _generate(
            service,
            photos=[OrdlakPhoto(media_type="image/jpeg", content=b"\xff\xd8fake-jpeg")],
        )

        content = client.calls[0]["messages"][0]["content"]
        image_blocks = [b for b in content if b["type"] == "image"]
        assert len(image_blocks) == 1
        assert image_blocks[0]["source"]["media_type"] == "image/jpeg"
        assert image_blocks[0]["source"]["type"] == "base64"

    async def test_zapisuje_liczbe_zdjec_ale_nie_zdjecia(self):
        service, _, _ = _service()

        draft = await _generate(
            service,
            photos=[
                OrdlakPhoto(media_type="image/png", content=b"a" * 100),
                OrdlakPhoto(media_type="image/png", content=b"b" * 100),
            ],
        )

        assert draft.generation.photo_count == 2
        assert not hasattr(draft.generation, "photos")

    async def test_wymusza_narzedzie_zamiast_wolnego_tekstu(self):
        service, client, _ = _service()

        await _generate(service)

        assert client.calls[0]["tool_choice"] == {
            "type": "tool",
            "name": "submit_offer_draft",
        }

    async def test_uzywa_modelu_z_konfiguracji(self):
        service, client, _ = _service()

        await _generate(service)

        assert client.calls[0]["model"] == "claude-sonnet-5"


class TestWalidacjaWejscia:
    async def test_pusta_notatka_odrzucona(self):
        service, _, _ = _service()

        with pytest.raises(OrdlakError, match="Notatka"):
            await _generate(service, note="   ")

    async def test_nieznany_stan_odrzucony(self):
        service, _, _ = _service()

        with pytest.raises(OrdlakError, match="Nieznany stan"):
            await _generate(service, condition="lekko_uzywany")

    async def test_czwarte_zdjecie_odrzucone(self):
        service, _, _ = _service()
        photos = [OrdlakPhoto("image/jpeg", b"x" * 10) for _ in range(4)]

        with pytest.raises(OrdlakError, match="Maksymalnie 3"):
            await _generate(service, photos=photos)

    async def test_za_duze_zdjecie_odrzucone(self):
        service, _, _ = _service(max_photo_size_mb=1)
        photos = [OrdlakPhoto("image/jpeg", b"x" * (2 * 1024 * 1024))]

        with pytest.raises(OrdlakError, match="limit to 1 MB"):
            await _generate(service, photos=photos)

    async def test_nieobslugiwany_format_zdjecia_odrzucony(self):
        service, _, _ = _service()
        photos = [OrdlakPhoto("application/pdf", b"%PDF-")]

        with pytest.raises(OrdlakError, match="nieobsługiwany format"):
            await _generate(service, photos=photos)

    async def test_bledna_prowizja_nie_wywoluje_modelu(self):
        """Zła kalkulacja ma paść przed zapytaniem, żeby nie płacić za AI."""
        service, client, _ = _service()

        with pytest.raises(OrdlakError, match="mniejsze niż 100%"):
            await _generate(service, commission_percent=70.0, target_margin_percent=40.0)

        assert client.calls == []


class TestJakoscOpisu:
    """
    Regresja: pierwsza wersja promptu była zbudowana z samych zakazów i model
    oddawał 5-linijkowy szkielet zamiast pełnej oferty. Te testy pilnują, że
    krótki opis jest wykrywany i ponawiany tak samo jak krótki tytuł.
    """

    async def test_krotki_opis_ponawia_zapytanie(self):
        client = _FakeAnthropic(
            responses=[
                _ok_response(description=KROTKI_OPIS),
                _ok_response(description=DOBRY_OPIS),
            ]
        )
        service, _, _ = _service(client)

        draft = await _generate(service)

        assert len(client.calls) == 2
        assert draft.generation.generated_description_html == DOBRY_OPIS

    async def test_ponowienie_mowi_wprost_ze_chodzi_o_opis(self):
        client = _FakeAnthropic(
            responses=[
                _ok_response(description=KROTKI_OPIS),
                _ok_response(description=DOBRY_OPIS),
            ]
        )
        service, _, _ = _service(client)

        await _generate(service)

        podpowiedz = client.calls[1]["system"]
        assert "OPIS miał tylko" in podpowiedz
        assert "TYTUŁ miał tylko" not in podpowiedz

    async def test_dwa_krotkie_opisy_zwracaja_dluzszy(self):
        """Gdy oba wyniki są słabe, oddajemy ten bogatszy - nie pierwszy z brzegu."""
        dluzszy = KROTKI_OPIS + "<p>Dodatkowy akapit z cechami produktu.</p>"
        client = _FakeAnthropic(
            responses=[
                _ok_response(description=KROTKI_OPIS),
                _ok_response(description=dluzszy),
            ]
        )
        service, _, _ = _service(client)

        draft = await _generate(service)

        assert draft.generation.generated_description_html == dluzszy

    async def test_prompt_wymusza_strukture_i_dlugosc(self):
        """Prompt musi POKAZYWAĆ wzorzec, nie tylko zakazywać - stąd te kotwice."""
        service, client, _ = _service()

        await _generate(service)

        system = client.calls[0]["system"]
        assert "minimum 1500 znaków" in system
        assert "SPECYFIKACJA TECHNICZNA" in system
        assert "ZASTOSOWANIE" in system
        assert "PRZYKŁAD" in system


class TestJakoscTytulu:
    async def test_krotki_tytul_ponawia_zapytanie_raz(self):
        client = _FakeAnthropic(
            responses=[_ok_response(title=KROTKI_TYTUL), _ok_response(title=DOBRY_TYTUL)]
        )
        service, _, _ = _service(client)

        draft = await _generate(service)

        assert len(client.calls) == 2
        assert draft.generation.generated_title == DOBRY_TYTUL
        assert draft.title_below_target is False

    async def test_dobry_tytul_nie_ponawia(self):
        service, client, _ = _service()

        await _generate(service)

        assert len(client.calls) == 1

    async def test_dwa_krotkie_tytuly_zwracaja_flage(self):
        """Lepszy krótszy trafny tytuł niż wymuszony bełkot - ale UI ma o tym wiedzieć."""
        client = _FakeAnthropic(
            responses=[_ok_response(title=KROTKI_TYTUL), _ok_response(title=KROTKI_TYTUL)]
        )
        service, _, _ = _service(client)

        draft = await _generate(service)

        assert len(client.calls) == 2
        assert draft.title_below_target is True

    async def test_ponowienie_dostaje_podpowiedz_w_promptcie(self):
        client = _FakeAnthropic(
            responses=[_ok_response(title=KROTKI_TYTUL), _ok_response(title=DOBRY_TYTUL)]
        )
        service, _, _ = _service(client)

        await _generate(service)

        assert "TYTUŁ miał tylko" in client.calls[1]["system"]
        assert "OPIS miał tylko" not in client.calls[1]["system"]
        assert "popraw poprzednią wersję" not in client.calls[0]["system"]


class TestBledyModelu:
    async def test_tytul_poza_limitem_regulaminowym_odrzucony(self):
        client = _FakeAnthropic(responses=[_ok_response(title="x" * 80)])
        service, _, _ = _service(client)

        with pytest.raises(OrdlakError, match="12-75"):
            await _generate(service)

    async def test_brak_bloku_tool_use_daje_czytelny_blad(self):
        client = _FakeAnthropic(
            responses=[
                _FakeResponse(content=[_FakeBlock(type="text")], stop_reason="end_turn")
            ]
        )
        service, _, _ = _service(client)

        with pytest.raises(OrdlakError, match="oczekiwanym formacie"):
            await _generate(service)

    async def test_odmowa_modelu_daje_czytelny_blad(self):
        client = _FakeAnthropic(responses=[_FakeResponse(content=[], stop_reason="refusal")])
        service, _, _ = _service(client)

        with pytest.raises(OrdlakError, match="odmówił"):
            await _generate(service)

    async def test_ucieta_odpowiedz_daje_czytelny_blad(self):
        client = _FakeAnthropic(
            responses=[_FakeResponse(content=[], stop_reason="max_tokens")]
        )
        service, _, _ = _service(client)

        with pytest.raises(OrdlakError, match="ucięta"):
            await _generate(service)

    async def test_blok_tool_use_bez_opisu_odrzucony(self):
        client = _FakeAnthropic(
            responses=[
                _FakeResponse(
                    content=[
                        _FakeBlock(
                            type="tool_use",
                            input={"title": DOBRY_TYTUL, "description_html": ""},
                        )
                    ]
                )
            ]
        )
        service, _, _ = _service(client)

        with pytest.raises(OrdlakError, match="niekompletną"):
            await _generate(service)

    async def test_pomija_bloki_nie_bedace_tool_use(self):
        """Odpowiedź może zawierać też blok tekstowy - liczy się tool_use."""
        client = _FakeAnthropic(
            responses=[
                _FakeResponse(
                    content=[
                        _FakeBlock(type="text"),
                        _FakeBlock(
                            type="tool_use",
                            input={
                                "title": DOBRY_TYTUL,
                                "description_html": OPIS,
                                "condition_notes": "",
                            },
                        ),
                    ]
                )
            ]
        )
        service, _, _ = _service(client)

        draft = await _generate(service)

        assert draft.generation.generated_title == DOBRY_TYTUL

    async def test_bledny_klucz_api_tlumaczony_na_polski(self):
        error = Exception("unauthorized")
        error.status_code = 401  # type: ignore[attr-defined]
        service, _, _ = _service(_FakeAnthropic(raise_error=error))

        with pytest.raises(OrdlakError, match="ANTHROPIC_API_KEY"):
            await _generate(service)

    async def test_limit_zapytan_tlumaczony_na_polski(self):
        error = Exception("rate limited")
        error.status_code = 429  # type: ignore[attr-defined]
        service, _, _ = _service(_FakeAnthropic(raise_error=error))

        with pytest.raises(OrdlakError, match="limit zapytań"):
            await _generate(service)


class TestBrakKonfiguracji:
    async def test_bez_klucza_api_czytelny_komunikat(self):
        service = OrdlakService(
            repository=FakeOrdlakRepository(),
            settings=OrdlakSettings(_env_file=None, ANTHROPIC_API_KEY=SecretStr("")),
        )

        with pytest.raises(OrdlakNotConfiguredError, match="ANTHROPIC_API_KEY"):
            await _generate(service)


class TestHistoriaIFinalizacja:
    async def test_historia_zwraca_najnowsze_pierwsze(self):
        service, _, _ = _service()
        await _generate(service, note="pierwszy produkt")
        await _generate(service, note="drugi produkt")

        historia = await service.history()

        assert len(historia) == 2
        assert historia[0].user_note == "drugi produkt"

    async def test_finalize_zapisuje_poprawki(self):
        service, _, _ = _service()
        draft = await _generate(service)
        assert draft.generation.id is not None

        updated = await service.finalize(
            draft.generation.id, "Poprawiony tytuł oferty", "<p>Poprawiony opis</p>"
        )

        assert updated is not None
        assert updated.title == "Poprawiony tytuł oferty"
        assert updated.description_html == "<p>Poprawiony opis</p>"
        # oryginał modelu zostaje w historii do porównania
        assert updated.generated_title == DOBRY_TYTUL

    async def test_finalize_nieistniejacej_generacji_zwraca_none(self):
        service, _, _ = _service()

        assert await service.finalize(999, "tytuł", "<p>opis</p>") is None
