/**
 * Szkielet aplikacji (sekcja 8 i 10 instrukcji "Nokturn"):
 *
 *   pasek tytulu 38 px
 *   pasek boczny 238 px | topbar 54 px
 *                       | obszar roboczy (flex:1, wlasne przewijanie)
 *
 * WYSOKOSC OKNA JEST STALA. Obszar roboczy rozciaga sie elastycznie
 * (`flex-1 min-h-0`), wiec aplikacja nie skacze przy zmianie zakladki.
 *
 * Pasek statystyk zniknal - kafle KPI mieszkaja teraz na ekranie Start,
 * gdzie sa czescia ukladu, a nie doklejonym pasem nad kazdym ekranem.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Sidebar, type NavCounts, type ViewId } from "../components/Sidebar";
import { Titlebar } from "../components/Titlebar";
import { Topbar, type TopbarAlert } from "../components/Topbar";
import { CommandPalette, type PaletteTarget } from "../components/CommandPalette";
import { useAuth } from "../lib/auth";
import { useSync } from "../lib/sync";
import { useOrdlakState } from "../lib/ordlakState";
import { formatLongDate, formatPlural } from "../lib/format";
import { isPendingOrder } from "../lib/fulfillment";
import { StartScreen } from "./StartScreen";
import { ZamowieniaScreen } from "./ZamowieniaScreen";
import { DiscussionsScreen } from "./DiscussionsScreen";
import { MagazynScreen } from "./MagazynScreen";
import { MailboxScreen } from "./MailboxScreen";
import { OrdlakScreen } from "./OrdlakScreen";
import { ReturnsScreen } from "./ReturnsScreen";
import { HurtowniaScreen } from "./HurtowniaScreen";
import { OlxScreen } from "./OlxScreen";
import { StatystykiScreen } from "./StatystykiScreen";
import { KalendarzScreen } from "./KalendarzScreen";
import { UstawieniaScreen } from "./UstawieniaScreen";

/** Skroty `G` + litera do ekranow. */
const GOTO_KEYS: Record<string, ViewId> = {
  s: "start",
  z: "zamowienia",
  d: "dyskusje",
  m: "magazyn",
  p: "poczta",
  w: "zwroty",
  o: "ordlak",
  h: "hurtownie",
  t: "statystyki",
  k: "kalendarz",
  u: "ustawienia",
};

/**
 * Statusy zwrotow, ktore nie wymagaja juz niczego od sprzedawcy - te same,
 * ktore ekran Zwroty pokazuje wygaszone (ton "mute").
 */
const CLOSED_RETURN_STATUSES = new Set(["COMMISSION_REFUNDED", "CANCELLED", "REJECTED"]);

function hostnameOf(baseUrl: string): string {
  try {
    return new URL(baseUrl).hostname;
  } catch {
    return baseUrl;
  }
}

export function ShellLayout() {
  const [view, setView] = React.useState<ViewId>("start");
  const [paletteOpen, setPaletteOpen] = React.useState(false);
  const [focusOrderId, setFocusOrderId] = React.useState<string | null>(null);
  const [focusOffer, setFocusOffer] = React.useState<string | null>(null);
  /** Pytanie przekazane z paska asystenta na ekranie Start. */
  const [assistantSeed, setAssistantSeed] = React.useState<string | null>(null);
  const { session } = useAuth();
  const { sync } = useSync();
  const { setAlert } = useOrdlakState();

  // --------------------------------------------------- dane do licznikow

  const dashboardQuery = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => {
      const result = await window.ordly.stats.dashboard();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    refetchInterval: 60_000,
  });

  const ordersQuery = useQuery({
    queryKey: ["orders"],
    queryFn: async () => {
      const result = await window.ordly.orders.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const issuesQuery = useQuery({
    queryKey: ["issues"],
    queryFn: async () => {
      const result = await window.ordly.issues.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    retry: false,
  });

  const mailQuery = useQuery({
    queryKey: ["mailbox", "all", false],
    queryFn: async () => {
      const result = await window.ordly.mailbox.list({});
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const returnsQuery = useQuery({
    queryKey: ["returns"],
    queryFn: async () => {
      const result = await window.ordly.returns.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    retry: false,
  });

  const openIssues = (issuesQuery.data ?? []).filter((issue) => issue.chat_active);
  const unreadMail = (mailQuery.data ?? []).filter((message) => !message.is_read);
  const pendingOrders = (ordersQuery.data ?? []).filter(isPendingOrder);
  // Licznik zwrotow to te, ktore jeszcze czekaja na ruch - nie wszystkie
  // pobrane (do 50), bo razem z zamknietymi wisial na stale.
  const openReturns = (returnsQuery.data ?? []).filter(
    (item) => !CLOSED_RETURN_STATUSES.has(item.status)
  );

  const counts: NavCounts = {
    zamowienia: pendingOrders.length,
    dyskusje: { value: openIssues.length, alert: openIssues.length > 0 },
    poczta: unreadMail.length,
    zwroty: openReturns.length,
  };

  // Brak lacznosci z Pi zapala alarm maskotki (sekcja 6). Pojedyncze
  // `isError` wystarczy - pulpit odpytuje Pi co minute, wiec blad znaczy,
  // ze ostatnia proba nie doszla.
  const piOffline =
    dashboardQuery.isError ||
    (dashboardQuery.data ? !dashboardQuery.data.marketplace_connection_ok : false);
  React.useEffect(() => {
    setAlert("pi", dashboardQuery.isError);
    setAlert("allegro", dashboardQuery.data?.marketplace_connection_ok === false);
  }, [dashboardQuery.isError, dashboardQuery.data?.marketplace_connection_ok, setAlert]);

  // ------------------------------------------------------------- skroty

  React.useEffect(() => {
    let gotoArmed = false;
    let gotoTimer = 0;

    function isTyping(target: EventTarget | null): boolean {
      const element = target as HTMLElement | null;
      if (!element) return false;
      return (
        element.tagName === "INPUT" ||
        element.tagName === "TEXTAREA" ||
        element.isContentEditable
      );
    }

    function handleKey(event: KeyboardEvent) {
      const key = event.key.toLowerCase();

      if ((event.ctrlKey || event.metaKey) && key === "k") {
        event.preventDefault();
        setPaletteOpen(true);
        return;
      }
      if ((event.ctrlKey || event.metaKey) && key === "r") {
        event.preventDefault();
        sync();
        return;
      }
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (isTyping(event.target)) return;

      if (key === "/") {
        event.preventDefault();
        setPaletteOpen(true);
        return;
      }
      if (gotoArmed) {
        gotoArmed = false;
        window.clearTimeout(gotoTimer);
        const target = GOTO_KEYS[key];
        if (target) {
          event.preventDefault();
          setView(target);
        }
        return;
      }
      if (key === "g") {
        gotoArmed = true;
        // Sekwencja wygasa po 1,2 s, zeby samotne "g" nie zjadalo
        // nastepnej litery wpisanej minute pozniej.
        gotoTimer = window.setTimeout(() => {
          gotoArmed = false;
        }, 1200);
      }
    }

    window.addEventListener("keydown", handleKey);
    return () => {
      window.removeEventListener("keydown", handleKey);
      window.clearTimeout(gotoTimer);
    };
  }, [sync]);

  const handlePaletteSelect = React.useCallback((target: PaletteTarget) => {
    if (target.kind === "view") {
      setView(target.view);
      return;
    }
    if (target.kind === "order") {
      setFocusOrderId(target.externalId);
      setView("zamowienia");
      return;
    }
    setFocusOffer(target.offerKey);
    setView("magazyn");
  }, []);

  const handleAsk = React.useCallback((questionText: string) => {
    setAssistantSeed(questionText);
    setView("ordlak");
  }, []);

  // ------------------------------------------------- tytuly i konteksty

  const crumbs: Record<ViewId, string> = {
    start: formatLongDate(new Date()),
    zamowienia: ordersQuery.data
      ? `Wszystkie kanały · ostatnie ${ordersQuery.data.length}`
      : "Wszystkie kanały",
    dyskusje: formatPlural(openIssues.length, [
      "otwarta sprawa",
      "otwarte sprawy",
      "otwartych spraw",
    ]),
    magazyn: "Wystawione oferty · stan wpisujesz ręcznie",
    poczta: "Skrzynka główna · IMAP",
    zwroty: formatPlural(openReturns.length, [
      "zwrot do obsłużenia",
      "zwroty do obsłużenia",
      "zwrotów do obsłużenia",
    ]),
    ordlak: "Asystent sprzedaży",
    hurtownie: "Dostawcy i zamówienia",
    olx: "Oferty prowadzone ręcznie",
    statystyki: "Ostatnie 7 dni",
    kalendarz: "Święta i okresy sprzedażowe",
    ustawienia: "Synchronizacja i połączenie",
  };

  const titles: Record<ViewId, string> = {
    start: "Start",
    zamowienia: "Zamówienia",
    dyskusje: "Dyskusje",
    magazyn: "Magazyn",
    poczta: "Poczta",
    zwroty: "Zwroty",
    ordlak: "Ordlak",
    hurtownie: "Hurtownie",
    olx: "OLX",
    statystyki: "Statystyki",
    kalendarz: "Kalendarz",
    ustawienia: "Ustawienia",
  };

  /**
   * Lista pod dzwonkiem. Kazda pozycja jest POLICZONA z danych i prowadzi
   * na ekran, ktory ja obsluguje - nie ma tu wpisow bez pokrycia.
   */
  const alerts: TopbarAlert[] = [];
  if (pendingOrders.length > 0) {
    alerts.push({
      id: "orders",
      label: formatPlural(pendingOrders.length, [
        "zamówienie do spakowania",
        "zamówienia do spakowania",
        "zamówień do spakowania",
      ]),
      detail: "Zamówienia",
      view: "zamowienia",
      hot: true,
    });
  }
  if (openIssues.length > 0) {
    alerts.push({
      id: "issues",
      label: formatPlural(openIssues.length, [
        "kupujący czeka na odpowiedź",
        "kupujących czeka na odpowiedź",
        "kupujących czeka na odpowiedź",
      ]),
      detail: "Dyskusje",
      view: "dyskusje",
      hot: true,
    });
  }
  if (openReturns.length > 0) {
    alerts.push({
      id: "returns",
      label: formatPlural(openReturns.length, [
        "zwrot do obsłużenia",
        "zwroty do obsłużenia",
        "zwrotów do obsłużenia",
      ]),
      detail: "Zwroty",
      view: "zwroty",
      hot: true,
    });
  }
  if (unreadMail.length > 0) {
    alerts.push({
      id: "mail",
      label: formatPlural(unreadMail.length, [
        "nieprzeczytany mail",
        "nieprzeczytane maile",
        "nieprzeczytanych maili",
      ]),
      detail: "Poczta",
      view: "poczta",
      hot: false,
    });
  }
  if (piOffline) {
    alerts.push({
      id: "pi",
      label: dashboardQuery.isError ? "Brak łączności z Pi" : "Allegro nie odpowiada",
      detail: "Ustawienia",
      view: "ustawienia",
      hot: true,
    });
  }

  const username = session?.username ?? "";

  return (
    <div className="flex h-screen flex-col bg-void text-text">
      <Titlebar
        online={dashboardQuery.data?.marketplace_connection_ok ?? !dashboardQuery.isError}
        hostname={session ? hostnameOf(session.baseUrl) : ""}
      />

      <div className="flex min-h-0 flex-1">
        <Sidebar
          active={view}
          onSelect={setView}
          counts={counts}
          hostname={session ? hostnameOf(session.baseUrl) : ""}
          version={`v${__APP_VERSION__}`}
        />

        <main className="flex min-w-0 flex-1 flex-col bg-base">
          <Topbar
            title={titles[view]}
            crumb={crumbs[view]}
            initials={username || "?"}
            alerts={alerts}
            onOpenPalette={() => setPaletteOpen(true)}
            onNavigate={setView}
          />

          <div key={view} className="animate-fade-up flex min-h-0 flex-1 flex-col">
            {view === "start" && (
              <StartScreen onNavigate={setView} onAsk={handleAsk} username={username} />
            )}
            {view === "zamowienia" && (
              <ZamowieniaScreen
                focusOrderId={focusOrderId}
                onFocusHandled={() => setFocusOrderId(null)}
              />
            )}
            {view === "dyskusje" && <DiscussionsScreen />}
            {view === "magazyn" && (
              <MagazynScreen
                focusOffer={focusOffer}
                onFocusHandled={() => setFocusOffer(null)}
              />
            )}
            {view === "poczta" && <MailboxScreen />}
            {view === "zwroty" && <ReturnsScreen />}
            {view === "ordlak" && (
              <OrdlakScreen
                seedQuestion={assistantSeed}
                onSeedHandled={() => setAssistantSeed(null)}
              />
            )}
            {view === "hurtownie" && <HurtowniaScreen />}
            {view === "olx" && <OlxScreen />}
            {view === "statystyki" && <StatystykiScreen />}
            {view === "kalendarz" && <KalendarzScreen />}
            {view === "ustawienia" && <UstawieniaScreen />}
          </div>
        </main>
      </div>

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onSelect={handlePaletteSelect}
      />
    </div>
  );
}
