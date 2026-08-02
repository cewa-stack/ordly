"""Wysyłka maili do hurtowni przez SMTP - jedyne miejsce z hasłem SMTP."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from email.message import EmailMessage
from typing import Any

import aiosmtplib
from loguru import logger

from app.core.config import SmtpSettings
from app.domain.exceptions.domain_exceptions import MailNotConfiguredError, MailSendError

SendMailFn = Callable[..., Awaitable[Any]]


class MailService:
    """
    Wysyła maile w imieniu sprzedawcy (dziś: zamówienia do hurtowni).

    Aplikacja desktopowa układa treść (adresat, temat, tekst) i woła
    endpoint - nigdy nie widzi hasła SMTP, tylko ten serwis w backendzie
    na Pi zna `SmtpSettings`.
    """

    def __init__(self, settings: SmtpSettings, send_fn: SendMailFn = aiosmtplib.send) -> None:
        """
        Args:
            settings: Konfiguracja SMTP.
            send_fn: Funkcja wysyłająca wiadomość - domyślnie `aiosmtplib.send`,
                nadpisywalna w testach fake'iem zamiast monkeypatchowania.
        """
        self._settings = settings
        self._send_fn = send_fn

    async def send(self, to: str, subject: str, body: str) -> None:
        """
        Wysyła pojedynczy mail tekstowy.

        Raises:
            MailNotConfiguredError: Gdy SMTP nie jest skonfigurowany w `.env`.
            MailSendError: Gdy połączenie/logowanie/wysyłka SMTP zawiedzie.
        """
        if not self._settings.enabled:
            raise MailNotConfiguredError()

        message = EmailMessage()
        message["From"] = self._settings.user
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        try:
            await self._send_fn(
                message,
                hostname=self._settings.host,
                port=self._settings.port,
                username=self._settings.user,
                password=self._settings.password.get_secret_value(),
                use_tls=self._settings.use_ssl,
                start_tls=not self._settings.use_ssl,
            )
        except (aiosmtplib.SMTPException, OSError) as exc:
            logger.error("Wysyłka maila do {} nie powiodła się: {}", to, exc)
            raise MailSendError(str(exc)) from exc
