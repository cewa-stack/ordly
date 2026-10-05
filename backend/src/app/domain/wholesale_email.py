"""
Maile do hurtowni składane na Pi - dla zamówień z ORDLy Control Hub.

Hurtownie i szablony edytuje się w aplikacji desktopowej; desktop wysyła
ich kopię na Pi (`PUT /api/v1/hub/wholesale/catalog`). Hub wybiera
hurtownię, szablon i pozycje, a mail składa i wysyła ORDLY - tymi samymi
regułami co desktop (`desktop/src/renderer/src/lib/wholesalerTemplate.ts`),
żeby mail z Huba wyglądał tak samo jak mail z komputera.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

#: Ilości na Hubie się nie zmienia - idzie ta, którą hurtownia ma zapisaną.
MIN_QUANTITY = 1

_CONTACT_TOKEN = re.compile(r"[ \t]*\{osoba_kontaktowa\}")


@dataclass(frozen=True, slots=True)
class WholesaleItem:
    """Pozycja asortymentu hurtowni: nazwa i ilość, którą zwykle się bierze."""

    name: str
    quantity: int


@dataclass(frozen=True, slots=True)
class Wholesaler:
    """Hurtownia z desktopu (kopia na Pi)."""

    id: str
    name: str
    email: str
    contact_person: str = ""
    items: tuple[WholesaleItem, ...] = ()
    template_id: str | None = None


@dataclass(frozen=True, slots=True)
class WholesaleTemplate:
    """Szablon maila z dwoma wariantami: zamówienie i zapytanie (bez pozycji)."""

    id: str
    name: str
    subject: str
    body: str
    inquiry_subject: str
    inquiry_body: str
    is_default: bool = False


@dataclass(frozen=True, slots=True)
class WholesaleCatalog:
    """Hurtownie i szablony w jednej wersji - `version` zmienia się przy każdej zmianie."""

    wholesalers: tuple[Wholesaler, ...] = ()
    templates: tuple[WholesaleTemplate, ...] = ()
    version: str = ""

    def wholesaler(self, wholesaler_id: str) -> Wholesaler | None:
        return next((w for w in self.wholesalers if w.id == wholesaler_id), None)

    def resolve_template(self, template_id: str | None) -> WholesaleTemplate | None:
        """Wybrany szablon, a gdy go nie ma - domyślny, a gdy i tego nie ma - pierwszy."""
        if not self.templates:
            return None
        return (
            next((t for t in self.templates if t.id == template_id), None)
            or next((t for t in self.templates if t.is_default), None)
            or self.templates[0]
        )


@dataclass(frozen=True, slots=True)
class WholesaleEmail:
    """Gotowy mail do hurtowni."""

    subject: str
    body: str
    inquiry: bool
    items: tuple[WholesaleItem, ...] = field(default_factory=tuple)

    @property
    def items_summary(self) -> str:
        """Ten sam skrót co w historii na desktopie."""
        if not self.items:
            return "wiadomość bez pozycji"
        return ", ".join(f"{item.name} x{item.quantity}" for item in self.items)

    @property
    def items_key(self) -> str:
        """Odcisk listy pozycji - do wykrycia tego samego zamówienia wysłanego drugi raz."""
        raw = json.dumps(sorted([item.name, item.quantity] for item in self.items))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def catalog_from_payload(payload: dict[str, Any], version: str) -> WholesaleCatalog:
    """Kopia z desktopu (format `wholesalers.json` / `wholesaler_templates.json`) -> katalog."""
    wholesalers = tuple(
        Wholesaler(
            id=str(raw["id"]),
            name=str(raw["name"]),
            email=str(raw["email"]),
            contact_person=str(raw.get("contactPerson") or ""),
            items=tuple(
                WholesaleItem(
                    name=str(item["name"]), quantity=max(MIN_QUANTITY, int(item["quantity"]))
                )
                for item in raw.get("items") or []
                if str(item.get("name") or "").strip()
            ),
            template_id=raw.get("templateId") or None,
        )
        for raw in payload.get("wholesalers") or []
    )
    templates = tuple(
        WholesaleTemplate(
            id=str(raw["id"]),
            name=str(raw["name"]),
            subject=str(raw["subject"]),
            body=str(raw["body"]),
            inquiry_subject=str(raw["inquirySubject"]),
            inquiry_body=str(raw["inquiryBody"]),
            is_default=raw.get("isDefault") is True,
        )
        for raw in payload.get("templates") or []
    )
    return WholesaleCatalog(wholesalers=wholesalers, templates=templates, version=version)


def catalog_version(payload: dict[str, Any]) -> str:
    """Krótki odcisk treści katalogu: Hub odsyła go z prośbą, żeby nie trafić w starą listę."""
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def render_wholesale_email(
    template: WholesaleTemplate,
    wholesaler: Wholesaler,
    items: tuple[WholesaleItem, ...],
    today: date,
) -> WholesaleEmail:
    """Mail z szablonu - lustro `renderWholesalerEmail` z desktopu."""
    inquiry = len(items) == 0
    subject = template.inquiry_subject if inquiry else template.subject
    body = template.inquiry_body if inquiry else template.body
    return WholesaleEmail(
        subject=_fill(subject, wholesaler, items, today).strip(),
        body=_fill(body, wholesaler, items, today),
        inquiry=inquiry,
        items=items,
    )


def _fill(
    text: str, wholesaler: Wholesaler, items: tuple[WholesaleItem, ...], today: date
) -> str:
    contact = wholesaler.contact_person.strip()
    items_list = "\n".join(f"- {item.name} - ilość: {item.quantity} szt." for item in items)
    if not items:
        products = ""
    elif len(items) == 1:
        products = items[0].name
    else:
        products = "kilka produktów"

    # Bez osoby kontaktowej znika też spacja przed znacznikiem:
    # "Dzień dobry {osoba_kontaktowa}," -> "Dzień dobry," (jak na desktopie).
    text = _CONTACT_TOKEN.sub(
        lambda match: match.group(0).replace("{osoba_kontaktowa}", contact) if contact else "",
        text,
    )
    return (
        text.replace("{hurtownia}", wholesaler.name)
        .replace("{lista_pozycji}", items_list)
        .replace("{produkty}", products)
        .replace("{data}", today.strftime("%d.%m.%Y"))
    )
