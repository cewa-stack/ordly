"""Testy jednostkowe MailService."""

from __future__ import annotations

from email.message import EmailMessage

import pytest
from pydantic import SecretStr

from app.core.config import SmtpSettings
from app.domain.exceptions.domain_exceptions import MailNotConfiguredError, MailSendError
from app.services.mail_service import MailService


def _configured_settings() -> SmtpSettings:
    return SmtpSettings(
        SMTP_HOST="smtp.gmail.com",
        SMTP_PORT=587,
        SMTP_USER="sklep@example.com",
        SMTP_PASS="haslo-aplikacji",
        SMTP_USE_SSL=False,
    )


class FakeSender:
    """Fake zastępujący aiosmtplib.send - śledzi wywołania bez realnej sieci."""

    def __init__(self, should_raise: Exception | None = None) -> None:
        self.should_raise = should_raise
        self.calls: list[EmailMessage] = []

    async def __call__(self, message: EmailMessage, **kwargs: object) -> None:
        if self.should_raise:
            raise self.should_raise
        self.calls.append(message)


class TestMailService:
    """Testy wysyłki maili do hurtowni."""

    @pytest.mark.asyncio
    async def test_rzuca_mail_not_configured_gdy_brak_konfiguracji(self):
        """Pusta konfiguracja SMTP powinna dać jasny błąd, nie próbę połączenia."""
        service = MailService(SmtpSettings(), send_fn=FakeSender())

        with pytest.raises(MailNotConfiguredError):
            await service.send("hurtownia@example.com", "Zamówienie", "Treść")

    @pytest.mark.asyncio
    async def test_wysyla_mail_z_poprawnymi_naglowkami(self):
        """Wysłany mail powinien mieć poprawne From/To/Subject i treść."""
        sender = FakeSender()
        service = MailService(_configured_settings(), send_fn=sender)

        await service.send("hurtownia@example.com", "Zamówienie #1", "Proszę o dostawę.")

        assert len(sender.calls) == 1
        message = sender.calls[0]
        assert message["To"] == "hurtownia@example.com"
        assert message["Subject"] == "Zamówienie #1"
        assert message["From"] == "sklep@example.com"
        assert "Proszę o dostawę." in message.get_content()

    @pytest.mark.asyncio
    async def test_tlumaczy_blad_smtp_na_mail_send_error(self):
        """Błąd z warstwy SMTP powinien być jasnym MailSendError, nie surowym wyjątkiem."""
        sender = FakeSender(should_raise=OSError("połączenie odrzucone"))
        service = MailService(_configured_settings(), send_fn=sender)

        with pytest.raises(MailSendError):
            await service.send("hurtownia@example.com", "Zamówienie", "Treść")


def test_smtp_settings_enabled_wymaga_hosta_uzytkownika_i_hasla():
    """SmtpSettings.enabled powinno być True tylko przy pełnej konfiguracji."""
    assert SmtpSettings().enabled is False
    assert SmtpSettings(SMTP_HOST="smtp.gmail.com", SMTP_USER="a@example.com").enabled is False
    assert (
        SmtpSettings(
            SMTP_HOST="smtp.gmail.com",
            SMTP_USER="a@example.com",
            SMTP_PASS=SecretStr("haslo"),
        ).enabled
        is True
    )
