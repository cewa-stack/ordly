/**
 * Szkielet aplikacji wg sekcji 4.1 specyfikacji.
 *
 *   chrome okna (40 px)
 *   pasek boczny 224 px | topbar
 *                       | pasek statystyk  <- TYLKO na ekranie Start
 *                       | obszar roboczy (flex:1, wlasne przewijanie)
 *
 * WYSOKOSC OKNA JEST STALA. Obszar roboczy rozciaga sie elastycznie
 * (`flex-1 min-h-0`), wiec pojawienie sie albo znikniecie paska
 * statystyk nie zmienia wysokosci okna - aplikacja nie skacze przy
 * zmianie zakladki (kryterium odbioru 10.1).
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Sidebar, type NavCounts, type ViewId } from "../components/Sidebar";
import { Titlebar } from "../components/Titlebar";
import { Topbar } from "../components/Topbar";
import { CommandPalette, type PaletteTarget } from "../components/CommandPalette";
import { StatStrip } from "../components/StatStrip";
import { useAuth } from "../lib/auth";
import { useSync } from "../lib/sync";
import { formatLongDate } from "../lib/format";
import { isPendingFulfillment } from "../lib/fulfillment";
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
import { UstawieniaScreen } from "./UstawieniaScreen";

/** Skroty `G` + litera do ekranow (sekcja 9.1 pkt 14). */
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
  u: "ustawienia",
};

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
  const [focusSku, setFocusSku] = React.useState<string | null>(null);
  const { session } = useAuth();
  const { sync } = useSync();

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
  const pendingOrders = (ordersQuery.data ?? []).filter((order) =>
    isPendingFulfillment(order.fulfillment_status)
  );
  const lowStockCount = dashboardQuery.data?.low_stock_count ?? 0;

  const counts: NavCounts = {
    zamowienia: pendingOrders.length,
    dyskusje: { value: openIssues.length, alert: openIssues.length > 0 },
    magazyn: { value: lowStockCount, alert: lowStockCount > 0 },
    poczta: unreadMail.length,
    zwroty: (returnsQuery.data ?? []).length,
  };

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
        // Sekwencja wygasa po 1.2 s, zeby samotne "g" nie zjadalo
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
    setFocusSku(target.sku);
    setView("magazyn");
  }, []);

  // ------------------------------------------------- tytuly i okruszki

  const crumbs: Record<ViewId, string> = {
    start: formatLongDate(new Date()),
    zamowienia: "Wszystkie kanały · ostatnie 20",
    dyskusje: `${openIssues.length} ${
      openIssues.length === 1 ? "otwarta sprawa" : "otwartych spraw"
    }`,
    magazyn: dashboardQuery.data
      ? `${lowStockCount} ${lowStockCount === 1 ? "pozycja" : "pozycji"} poniżej progu`
      : "Wczytuję stan magazynu…",
    poczta: "Skrzynka główna · IMAP",
    zwroty: "Ostatnie 30 dni",
    ordlak: "Generator ofert Allegro",
    hurtownie: "Dostawcy i zamówienia",
    olx: "Oferty prowadzone ręcznie",
    statystyki: "Ostatnie 7 dni",
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
    ustawienia: "Ustawienia",
  };

  const initials = (session?.username ?? "?").slice(0, 2).toUpperCase();

  return (
    <div className="flex h-screen flex-col bg-panel text-white">
      <Titlebar
        online={dashboardQuery.data?.marketplace_connection_ok ?? !dashboardQuery.isError}
        hostname={session ? hostnameOf(session.baseUrl) : ""}
      />

      <div className="flex min-h-0 flex-1">
        <Sidebar active={view} onSelect={setView} counts={counts} />

        <main className="flex min-w-0 flex-1 flex-col">
          <Topbar
            title={titles[view]}
            crumb={crumbs[view]}
            initials={initials}
            onOpenPalette={() => setPaletteOpen(true)}
          />

          {/* Pasek statystyk widoczny WYLACZNIE na ekranie Start. */}
          {view === "start" && (
            <StatStrip
              dashboard={dashboardQuery.data}
              openIssues={openIssues.length}
              loading={dashboardQuery.isLoading}
            />
          )}

          <div key={view} className="animate-fade-up flex min-h-0 flex-1 flex-col">
            {view === "start" && <StartScreen onNavigate={setView} />}
            {view === "zamowienia" && (
              <ZamowieniaScreen
                focusOrderId={focusOrderId}
                onFocusHandled={() => setFocusOrderId(null)}
              />
            )}
            {view === "dyskusje" && <DiscussionsScreen />}
            {view === "magazyn" && (
              <MagazynScreen focusSku={focusSku} onFocusHandled={() => setFocusSku(null)} />
            )}
            {view === "poczta" && <MailboxScreen />}
            {view === "zwroty" && <ReturnsScreen />}
            {view === "ordlak" && <OrdlakScreen />}
            {view === "hurtownie" && <HurtowniaScreen />}
            {view === "olx" && <OlxScreen />}
            {view === "statystyki" && <StatystykiScreen />}
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
