/**
 * Ustawienia (sekcja 9.1 pkt 2) - wiersz: tytul, opis, kontrolka po prawej.
 *
 * ZAKRES JEST WYZNACZONY PRZEZ BACKEND, nie przez zyczenia. Kazdy wiersz
 * tutaj albo cos realnie robi, albo jawnie mowi, ze zmiane wykonuje sie
 * na Pi i pokazuje dokladna komende. Zero przelacznikow, ktore nic nie
 * zmieniaja - patrz [[feedback-no-phantom-features]].
 *
 * Progi niskiego stanu sa edytowalne, bo backend ma dla nich operacje
 * `op: "min"` w `POST /api/v1/stock/{sku}/adjust`.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckIcon, RefreshIcon } from "../icons";
import { Button, MiniButton, SectionLabel, SkeletonRows } from "../components/ui";
import { ConfirmDialog } from "../components/Modal";
import { useAuth } from "../lib/auth";
import { useToast } from "../lib/toast";
import { formatDateTime } from "../lib/format";

function Row({
  title,
  description,
  children,
}: {
  title: string;
  description: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-4 rounded-md border border-line bg-panel-2 px-[17px] py-[15px]">
      <div className="min-w-0 flex-1">
        <h4 className="mb-[3px] text-[13px] font-semibold">{title}</h4>
        <p className="text-[11.5px] leading-[1.45] text-slate-dim">{description}</p>
      </div>
      {children}
    </div>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return <code className="o-mono text-[11px] text-slate">{children}</code>;
}

function ThresholdEditor() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [drafts, setDrafts] = React.useState<Record<string, string>>({});

  const stockQuery = useQuery({
    queryKey: ["stock"],
    queryFn: async () => {
      const result = await window.ordly.stock.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const saveMutation = useMutation({
    mutationFn: async ({ sku, value }: { sku: string; value: number }) => {
      const result = await window.ordly.stock.adjust(sku, { op: "min", quantity: value });
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (item) => {
      void queryClient.invalidateQueries({ queryKey: ["stock"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[item.sku];
        return next;
      });
      toast.success("Zapisano próg", `${item.sku} · ostrzeżenie poniżej ${item.min_stock}`);
    },
    onError: (error) => {
      toast.error(
        "Nie udało się zapisać progu",
        error instanceof Error ? error.message : "Spróbuj ponownie."
      );
    },
  });

  if (stockQuery.isLoading) return <SkeletonRows rows={3} />;

  return (
    <div className="flex flex-col gap-2">
      {(stockQuery.data ?? []).map((item) => {
        const draft = drafts[item.sku];
        const changed = draft !== undefined && Number(draft) !== item.min_stock;
        return (
          <div
            key={item.sku}
            className="flex items-center gap-3 rounded-md border border-line bg-panel-2 px-[17px] py-3"
          >
            <span className="min-w-0 flex-1 truncate text-[12.5px] text-white">{item.name}</span>
            <span className="o-mono w-20 shrink-0 text-[11px] text-slate-dim">{item.sku}</span>
            <span className="o-mono shrink-0 text-[11px] text-slate-dim">stan {item.stock}</span>
            <input
              type="number"
              min={0}
              value={draft ?? String(item.min_stock)}
              onChange={(event) =>
                setDrafts((prev) => ({ ...prev, [item.sku]: event.target.value }))
              }
              aria-label={`Próg niskiego stanu dla ${item.sku}`}
              className="o-mono w-[72px] shrink-0 rounded-sm border border-line bg-ink-raised px-2 py-1.5 text-center text-[12px] text-white outline-none focus:border-teal-bright"
            />
            <MiniButton
              icon={<CheckIcon size={13} />}
              disabled={!changed || saveMutation.isPending}
              onClick={() =>
                saveMutation.mutate({ sku: item.sku, value: Math.max(0, Number(draft)) })
              }
            >
              Zapisz
            </MiniButton>
          </div>
        );
      })}
    </div>
  );
}

export function UstawieniaScreen() {
  const { session, logout } = useAuth();
  const toast = useToast();
  const [logoutConfirm, setLogoutConfirm] = React.useState(false);

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const result = await window.ordly.stats.health();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    refetchInterval: 30_000,
  });

  const mailStatusQuery = useQuery({
    queryKey: ["mailbox-status"],
    queryFn: async () => {
      const result = await window.ordly.mailbox.status();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    retry: false,
  });

  const backupMutation = useMutation({
    mutationFn: async () => {
      const result = await window.ordly.stats.backup();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (result) => {
      toast.success("Kopia zapasowa utworzona", result.backup_path);
    },
    onError: (error) => {
      toast.error(
        "Backup się nie udał",
        error instanceof Error ? error.message : "Sprawdź logi usługi ordly na Pi."
      );
    },
  });

  const health = healthQuery.data;
  const mail = mailStatusQuery.data;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto p-[22px]">
      <SectionLabel>Połączenie</SectionLabel>

      <Row
        title="Raspberry Pi"
        description={
          health ? (
            <>
              Działa od {health.uptime} · ostatnia synchronizacja {health.last_sync} · baza{" "}
              {health.database_ok ? "sprawna" : "niedostępna"}
            </>
          ) : (
            "Sprawdzam stan backendu…"
          )
        }
      >
        <span className="o-mono shrink-0 text-[11px] text-slate-dim">
          {session ? new URL(session.baseUrl).hostname : ""}
        </span>
      </Row>

      <Row
        title="Konto Allegro"
        description={
          health?.marketplace_connection_ok ? (
            "Token jest ważny - ORDLY pobiera zamówienia, zwroty i dyskusje."
          ) : (
            <>
              Brak ważnego tokenu. Zaloguj się ponownie na Pi:{" "}
              <Code>cd ~/ordly/backend &amp;&amp; uv run python scripts/allegro_login.py</Code>{" "}
              (przez tunel <Code>ssh -L 53682:localhost:53682</Code>).
            </>
          )
        }
      >
        <span
          className={`o-mono shrink-0 rounded-[20px] px-2.5 py-1 text-[10.5px] ${
            health?.marketplace_connection_ok
              ? "bg-teal-dim text-teal-bright"
              : "bg-coral-dim text-coral"
          }`}
        >
          {health?.marketplace_connection_ok ? "połączone" : "brak tokenu"}
        </span>
      </Row>

      <Row
        title="Skrzynka IMAP"
        description={
          mail?.configured ? (
            <>
              {mail.host} jako {mail.user_masked} · obserwowani nadawcy:{" "}
              {mail.watch_senders.join(", ")} · {mail.message_count} wiadomości w bazie
              {mail.last_received_at
                ? `, ostatnia ${formatDateTime(mail.last_received_at)}`
                : ""}
            </>
          ) : (
            <>
              Nieskonfigurowana. Uzupełnij <Code>IMAP_USER</Code> i <Code>IMAP_PASS</Code> w{" "}
              <Code>~/ordly/backend/.env</Code>, potem{" "}
              <Code>sudo systemctl restart ordly</Code>. Gmail wymaga hasła aplikacji.
            </>
          )
        }
      >
        <span
          className={`o-mono shrink-0 rounded-[20px] px-2.5 py-1 text-[10.5px] ${
            mail?.configured ? "bg-teal-dim text-teal-bright" : "bg-coral-dim text-coral"
          }`}
        >
          {mail?.configured ? "podłączona" : "wyłączona"}
        </span>
      </Row>

      <Row
        title="Harmonogram synchronizacji"
        description={
          <>
            Zamówienia co 60 s, skrzynka co 5 min, kopia zapasowa codziennie o 3:00. Zmiana
            wymaga edycji <Code>.env</Code> na Pi i restartu usługi.
          </>
        }
      >
        <MiniButton
          icon={<RefreshIcon size={13} />}
          onClick={() => void healthQuery.refetch()}
          disabled={healthQuery.isFetching}
        >
          Odśwież stan
        </MiniButton>
      </Row>

      <Row
        title="Kopia zapasowa bazy"
        description="Tworzy kopię bazy SQLite na Pi (poza harmonogramem). Przywracanie robi się ręcznie z pliku - ORDLY celowo nie nadpisuje bazy z aplikacji."
      >
        <Button
          variant="ghost"
          onClick={() => backupMutation.mutate()}
          disabled={backupMutation.isPending}
        >
          {backupMutation.isPending ? "Tworzę…" : "Utwórz kopię teraz"}
        </Button>
      </Row>

      <div className="mt-4">
        <SectionLabel>Progi niskiego stanu</SectionLabel>
        <p className="mb-2 mt-1 text-[11.5px] text-slate-dim">
          Poniżej tej liczby Ordi oznacza produkt jako wymagający uzupełnienia i podpowiada go
          przy zamówieniu do hurtowni.
        </p>
        <ThresholdEditor />
      </div>

      <div className="mt-4">
        <SectionLabel>Sesja</SectionLabel>
      </div>
      <Row
        title="Wylogowanie"
        description={`Zalogowany jako ${session?.username ?? "?"}. Token zostanie usunięty z tego komputera.`}
      >
        <Button
          variant="ghost"
          onClick={() => setLogoutConfirm(true)}
          className="!text-coral"
        >
          Wyloguj
        </Button>
      </Row>

      <ConfirmDialog
        open={logoutConfirm}
        title="Wylogować się?"
        message="Token dostępu zostanie usunięty z tego komputera. Żeby wrócić, podasz adres Pi oraz login i hasło."
        confirmLabel="Wyloguj"
        onConfirm={() => void logout()}
        onClose={() => setLogoutConfirm(false)}
      />
    </div>
  );
}
