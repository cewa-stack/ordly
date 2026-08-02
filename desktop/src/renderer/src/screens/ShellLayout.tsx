import * as React from "react";
import { Sidebar, type ViewId } from "../components/Sidebar";
import { Titlebar } from "../components/Titlebar";
import { CommandPalette } from "../components/CommandPalette";
import { useAuth } from "../lib/auth";
import { MagazynScreen } from "./MagazynScreen";
import { ZamowieniaScreen } from "./ZamowieniaScreen";
import { ReturnsScreen } from "./ReturnsScreen";
import { DiscussionsScreen } from "./DiscussionsScreen";
import { HurtowniaScreen } from "./HurtowniaScreen";
import { MailboxScreen } from "./MailboxScreen";
import { OlxScreen } from "./OlxScreen";
import { StatystykiScreen } from "./StatystykiScreen";

function hostnameOf(baseUrl: string): string {
  try {
    return new URL(baseUrl).hostname;
  } catch {
    return baseUrl;
  }
}

export function ShellLayout() {
  const [view, setView] = React.useState<ViewId>("magazyn");
  const [paletteOpen, setPaletteOpen] = React.useState(false);
  const { session } = useAuth();

  React.useEffect(() => {
    function handleShortcut(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
    }
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  return (
    <div className="flex h-screen flex-col bg-background text-text">
      <Titlebar
        status={
          <div className="flex items-center gap-3">
            <button
              onClick={() => setPaletteOpen(true)}
              className="app-region-no-drag flex h-6 items-center gap-2 rounded-md border border-border bg-background px-2 text-[10.5px] text-text-dim hover:border-primary-border hover:text-text-secondary"
            >
              Szukaj…
              <kbd className="rounded border border-border bg-surface-raised px-1 font-mono text-[9px]">
                Ctrl K
              </kbd>
            </button>
            <div className="flex items-center gap-1.5 font-mono text-[10.5px] text-text-dim">
              <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-success" />
              {session ? hostnameOf(session.baseUrl) : ""}
            </div>
          </div>
        }
      />
      <div className="flex min-h-0 flex-1">
        <Sidebar active={view} onSelect={setView} />
        <main className="min-w-0 flex-1 overflow-y-auto p-7">
          {view === "magazyn" && <MagazynScreen />}
          {view === "zamowienia" && <ZamowieniaScreen />}
          {view === "zwroty" && <ReturnsScreen />}
          {view === "dyskusje" && <DiscussionsScreen />}
          {view === "hurtownia" && <HurtowniaScreen />}
          {view === "skrzynka" && <MailboxScreen />}
          {view === "olx" && <OlxScreen />}
          {view === "statystyki" && <StatystykiScreen />}
        </main>
      </div>

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onNavigate={(v) => setView(v)}
      />
    </div>
  );
}
