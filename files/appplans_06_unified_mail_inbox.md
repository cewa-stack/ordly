# APPPLANS 06 — Zakładka: Wszystkie maile Allegro/OLX

> Zależności: `appplans_02_sync_engine.md`.

## 1. Doprecyzowanie wymagania (ważne)

Wymaganie brzmi "zakładka gdzie widać wszystkie maile od allegro/olx pobrane z iOS Mail".
**Techniczne uściślenie:** nie ma publicznego API pozwalającego aplikacji desktopowej/RPi
"podłączyć się" bezpośrednio do appki Mail na iPhonie — Apple nie udostępnia takiego API dla
zewnętrznych integracji. To, co faktycznie można zrobić, i co realizuje ten sam cel
użytkownika, to: **podłączyć się przez IMAP bezpośrednio do skrzynki pocztowej** (tego samego
konta e-mail, które jest skonfigurowane w Mail na iPhonie — np. iCloud, Gmail, Outlook).
Efekt dla użytkownika jest identyczny: te same maile co widzi w telefonie, tylko czytane przez
IMAP zamiast przez appkę Mail.

**Przed startem tego modułu ustalić z użytkownikiem:**
- Jakiego dostawcy poczty używa (iCloud / Gmail / Outlook / inny) — bo różni się sposób
  generowania hasła aplikacji i adres serwera IMAP.
- iCloud Mail wymaga wygenerowania "hasła dedykowanego do aplikacji" w ustawieniach Apple ID
  (2FA musi być włączone).

## 2. Backend (Comcio) — nowy moduł IMAP

```python
# app/services/mail_watcher.py
import aioimaplib

class MailWatcher:
    def __init__(self, host: str, user: str, password: str):
        self.host = host
        self.user = user
        self.password = password

    async def fetch_new_from_senders(self, senders: list[str], since: datetime) -> list[MailDTO]:
        client = aioimaplib.IMAP4_SSL(host=self.host)
        await client.wait_hello_from_server()
        await client.login(self.user, self.password)
        await client.select("INBOX")
        # budowa filtra po nadawcy + dacie, jeden query per sender (IMAP SEARCH nie zawsze
        # wspiera OR czytelnie na wszystkich serwerach — bezpieczniej iterować)
        results = []
        for sender in senders:
            _, data = await client.search(f'FROM "{sender}" SINCE {since:%d-%b-%Y}')
            for msg_id in data[0].split():
                _, msg_data = await client.fetch(msg_id, "(RFC822)")
                results.append(MailDTO.from_raw(msg_data))
        await client.logout()
        return results
```

**Nadawcy do filtrowania (konfigurowalne w `.env` jako lista, nie hardcode):**
```
MAIL_WATCH_SENDERS=allegro.pl,noreply@allegromail.pl,olx.pl,noreply@olx.pl
```
Dopracować dokładne domeny/adresy nadawców na podstawie realnych maili w skrzynce
użytkownika (poprosić o przykład nagłówka `From:` z rzeczywistego maila od Allegro/OLX zamiast
zgadywać dokładny adres).

## 3. Podpięcie do sync cycle

`MailWatcher.fetch_new_from_senders` jest wywoływany w `run_sync_cycle` (z `appplans_02`) —
ale NIE co 60s jak reszta (IMAP przy zbyt częstym pollingu bywa throttlowany przez
dostawców pocztowych, zwłaszcza iCloud). Dodać osobny interwał, np. co 5 minut:

```python
@scheduler.scheduled_job("interval", minutes=5, id="mail_sync", max_instances=1)
async def run_mail_sync():
    watcher = MailWatcher(...)
    new_mails = await watcher.fetch_new_from_senders(senders, since=last_check)
    for mail in new_mails:
        await persist_mail(mail)
        await event_bus.publish({"type": "new_mail", "data": mail.summary()})
```

## 4. Nowa tabela

```python
class MailMessage(Base):
    __tablename__ = "mail_messages"
    id: Mapped[str] = mapped_column(primary_key=True)  # Message-ID z nagłówka
    sender: Mapped[str]
    subject: Mapped[str]
    received_at: Mapped[datetime]
    source: Mapped[str]  # "allegro" | "olx" | "other"
    body_preview: Mapped[str]  # pierwsze ~500 znaków, nie cała treść (oszczędność miejsca)
    is_read: Mapped[bool] = mapped_column(default=False)
    raw_available: Mapped[bool] = mapped_column(default=False)  # czy pełna treść jest cachowana
```
Klasyfikacja `source` po domenie nadawcy (prosta funkcja `classify_sender(sender: str) -> str`).

## 5. REST endpointy

```
GET  /api/v1/mail?source=allegro&unread_only=true&limit=&offset=
GET  /api/v1/mail/{id}          # pełna treść (fetch on-demand przez IMAP, nie cache'owane od razu)
POST /api/v1/mail/{id}/mark-read
```
Pełna treść maila pobierana on-demand (nie cache'ować wszystkiego od razu w SQLite — maile z
załącznikami mogą być duże; cache'ować tylko podgląd + metadane, treść pełną fetch'ować
leniwie i można ją cache'ować krótkoterminowo w pamięci).

## 6. UI Desktop — zakładka "Skrzynka"

```
src/features/mailbox/
  MailboxView.tsx      // lista maili, filtr źródła (Allegro/OLX/Wszystkie), filtr nieprzeczytane
  MailDetailPane.tsx    // podgląd treści wybranego maila (split view: lista | podgląd)
```
- Split-view layout: lista po lewej, podgląd po prawej (jak klient pocztowy).
- Badge z liczbą nieprzeczytanych w menu bocznym, aktualizowany przez event `new_mail`.
- Kliknięcie maila → `mark-read` + odświeżenie badge'a.
- Link "Otwórz w przeglądarce/Mail" jeśli user chce zobaczyć oryginał w swoim kliencie poczty.

## 7. Bezpieczeństwo — hasło do skrzynki

Hasło aplikacji IMAP jest jednym z najbardziej wrażliwych sekretów w całym projekcie (dostęp
do całej prywatnej skrzynki). Zasady:
- Przechowywane WYŁĄCZNIE w `.env` na Raspberry Pi, nigdy nie przesyłane do desktop/mobile.
- Desktop/mobile widzą tylko przetworzone dane (nadawca, temat, preview) przez REST API
  Comcio — nigdy surowe dane logowania IMAP.
- Rozważyć ograniczenie zakresu dostępu jeśli dostawca poczty na to pozwala (np. konto z
  dostępem tylko do jednego folderu, jeśli iCloud/Gmail to wspiera przez reguły
  przekierowania do dedykowanego folderu "Allegro-OLX" — to jest bezpieczniejsze niż czytanie
  całej skrzynki i warte rozważenia jako krok 0 tego modułu razem z użytkownikiem).

## 8. Testy wymagane

- Unit: `classify_sender` — poprawna klasyfikacja domen Allegro/OLX/inne.
- Unit: `MailDTO.from_raw` — parsowanie przykładowego surowego RFC822 (fixture).
- Integration: `run_mail_sync` na testowym koncie IMAP (np. konto testowe Gmail) — wykrywa
  nowy mail, tworzy rekord, emituje event.
- Manualny test bezpieczeństwa: potwierdzić że `grep -r IMAP_PASSWORD` w kodzie desktop/mobile
  nie zwraca wyników.

## 9. Definition of Done

- [ ] Ustalono z użytkownikiem dostawcę poczty i sposób generowania hasła aplikacji.
- [ ] IMAP sync działa co 5 minut, klasyfikuje maile Allegro/OLX poprawnie.
- [ ] Zakładka "Skrzynka" w desktop z podglądem i oznaczaniem jako przeczytane.
- [ ] Hasło IMAP istnieje tylko w `.env` na RPi, potwierdzone grepem w buildach klientów.
- [ ] Rozważona (i udokumentowana decyzja) opcja ograniczenia dostępu do dedykowanego folderu.
