/**
 * Poczta - uklad "nawigacja + tresc" (`300px 1fr`, sekcja 4.3).
 *
 * NAPRAWA: wczesniej pusta lista maili zawsze wygladala tak samo -
 * "Brak maili do pokazania" - niezaleznie od tego, czy IMAP byl w ogole
 * skonfigurowany na Pi. Teraz ekran pyta backend o `/api/v1/mail/status`
 * i mowi wprost, co jest nie tak i co z tym zrobic (sekcja 7.3).
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertIcon, ExternalIcon, RefreshIcon } from "../icons";
import {
  Button,
  Chip,
  EmptyState,
  ErrorState,
  InitialAvatar,
  MiniButton,
  SkeletonRows,
} from "../components/ui";
import { Mascot } from "../components/Mascot";
import { useToast } from "../lib/toast";
import { formatDateTime, formatTime } from "../lib/format";
import type { MailMessage } from "../types/api";

type SourceFilter = "all" | "allegro" | "olx";

const SOURCE_LABEL: Record<string, string> = {
  all: "Wszystkie",
  allegro: "Allegro",
  olx: "OLX",
  other: "Inne",
};

/** Otwiera pelna tresc maila w Gmailu - ORDLY cache'uje tylko podglad. */
function gmailSearchUrl(messageId: string): string {
  const cleaned = messageId.replace(/[<>]/g, "");
  return `https://mail.google.com/mail/u/0/#search/rfc822msgid:${encodeURIComponent(cleaned)}`;
}

/** Nadawca w formie "Allegro <noreply@allegro.pl>" -> sama nazwa. */
function senderName(sender: string): string {
  const match = sender.match(/^\s*"?([^"<]+?)"?\s*</);
  return (match?.[1] ?? sender).trim();
}

function senderAddress(sender: string): string {
  const match = sender.match(/<([^>]+)>/);
  return match?.[1] ?? sender;
}

/**
 * Panel diagnostyczny - pokazywany tylko wtedy, gdy naprawde nie ma
 * czego pokazac. Mowi konkretnie, ktora zmienna w `.env` na Pi jest
 * pusta, zamiast ogolnikowego "brak wiadomosci".
 */
function MailboxDiagnostics({ onSync, syncing }: { onSync: () => void; syncing: boolean }) {
  const statusQuery = useQuery({
    queryKey: ["mailbox-status"],
    queryFn: async () => {
      const result = await window.ordly.mailbox.status();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  if (statusQuery.isLoading) {
    return <span className="o-skeleton-bar mx-auto mt-14 h-24 w-[60%]" />;
  }

  if (statusQuery.isError) {
    return (
      <ErrorState
        title="Nie udało się sprawdzić skrzynki"
        detail={`Backend na Pi nie odpowiedział na zapytanie o stan skrzynki. Jeśli w treści widzisz 404, na Pi działa jeszcze stara wersja backendu - wgraj aktualizację i zrestartuj usługę ordly. ${
          statusQuery.error instanceof Error ? statusQuery.error.message : ""
        }`}
        onRetry={() => void statusQuery.refetch()}
      />
    );
  }

  const status = statusQuery.data;
  if (!status) return null;

  if (!status.configured) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 px-8 py-14 text-center">
        <Mascot pose="think" size={88} />
        <h4 className="o-display text-[15px] font-semibold">Skrzynka nie jest podłączona</h4>
        <p className="max-w-[420px] text-[12.5px] leading-[1.6] text-slate-dim">
          Backend na Pi nie ma ustawionego konta IMAP, więc nie ma skąd pobierać maili.
          Uzupełnij <code className="o-mono text-slate">IMAP_USER</code> i{" "}
          <code className="o-mono text-slate">IMAP_PASS</code> w pliku{" "}
          <code className="o-mono text-slate">~/ordly/backend/.env</code>, a potem zrestartuj
          usługę: <code className="o-mono text-slate">sudo systemctl restart ordly</code>.
        </p>
        <p className="max-w-[420px] text-[11.5px] leading-[1.6] text-slate-dim">
          Gmail i iCloud wymagają <b className="text-slate">hasła aplikacji</b> (przy włączonym
          2FA) - zwykłe hasło konta zostanie odrzucone.
        </p>
        <div className="o-mono mt-1 flex flex-col gap-1 rounded-md border border-line bg-panel-2 px-4 py-3 text-[10.5px] text-slate-dim">
          <span>serwer: {status.host || "(pusty)"}</span>
          <span>konto: {status.user_masked || "(puste)"}</span>
          <span>obserwowani nadawcy: {status.watch_senders.join(", ") || "(brak)"}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center gap-4 px-8 py-14 text-center">
      <Mascot pose="happy" size={88} />
      <h4 className="o-display text-[15px] font-semibold">Skrzynka podłączona, pusto</h4>
      <p className="max-w-[420px] text-[12.5px] leading-[1.6] text-slate-dim">
        ORDLY jest połączony z {status.host} jako {status.user_masked}, ale nie znalazł jeszcze
        maili od obserwowanych nadawców ({status.watch_senders.join(", ")}). Sprawdź teraz albo
        poczekaj - Ordi zagląda do skrzynki co 5 minut.
      </p>
      <Button
        onClick={onSync}
        disabled={syncing}
        icon={<RefreshIcon size={14} className={syncing ? "animate-spin-ring" : ""} />}
      >
        {syncing ? "Sprawdzam skrzynkę…" : "Sprawdź skrzynkę teraz"}
      </Button>
    </div>
  );
}

export function MailboxScreen() {
  const [source, setSource] = React.useState<SourceFilter>("all");
  const [unreadOnly, setUnreadOnly] = React.useState(false);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const queryClient = useQueryClient();
  const toast = useToast();

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["mailbox", source, unreadOnly],
    queryFn: async () => {
      const result = await window.ordly.mailbox.list({
        source: source === "all" ? undefined : source,
        unreadOnly,
      });
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const syncMutation = useMutation({
    mutationFn: async () => {
      const result = await window.ordly.mailbox.sync();
      if (!result.ok) {
        throw new Error(
          result.status === 404
            ? "Na Pi działa starsza wersja backendu - endpoint /api/v1/mail/sync jeszcze nie istnieje. Wgraj aktualizację i zrestartuj usługę ordly."
            : result.message
        );
      }
      return result.data;
    },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["mailbox"] });
      void queryClient.invalidateQueries({ queryKey: ["mailbox-status"] });
      if (!result.configured) {
        toast.error(
          "Skrzynka nie jest podłączona",
          "Uzupełnij IMAP_USER i IMAP_PASS w .env na Pi."
        );
      } else if (result.new_count === 0) {
        toast.success("Skrzynka sprawdzona", "Brak nowych wiadomości");
      } else {
        toast.success(
          "Skrzynka sprawdzona",
          `${result.new_count} ${result.new_count === 1 ? "nowa wiadomość" : "nowych wiadomości"}`
        );
      }
    },
    onError: (error) => {
      toast.error(
        "Skrzynka nie odpowiedziała",
        error instanceof Error ? error.message : "Sprawdź konfigurację IMAP na Pi."
      );
    },
  });

  const markReadMutation = useMutation({
    mutationFn: async (messageId: string) => {
      const result = await window.ordly.mailbox.markRead(messageId);
      if (!result.ok) throw new Error(result.message);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["mailbox"] });
    },
  });

  function handleSelect(message: MailMessage) {
    setSelectedId(message.message_id);
    if (!message.is_read) markReadMutation.mutate(message.message_id);
  }

  const selected = (data ?? []).find((message) => message.message_id === selectedId);

  if (isError) {
    return (
      <ErrorState
        title="Nie udało się pobrać skrzynki"
        detail={`Pi nie odpowiedziało na zapytanie o listę maili. ${
          error instanceof Error ? error.message : ""
        }`}
        onRetry={() => void refetch()}
      />
    );
  }

  // Pusta lista przy filtrze "Wszystkie" i bez filtra nieprzeczytanych
  // to jedyny przypadek, w ktorym warto pokazac pelna diagnostyke -
  // przy zawezonym filtrze pustka jest normalnym wynikiem filtrowania.
  const showDiagnostics =
    !isLoading && (data ?? []).length === 0 && source === "all" && !unreadOnly;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-[22px] py-[11px]">
        {(["all", "allegro", "olx"] as const).map((option) => (
          <Chip key={option} active={source === option} onClick={() => setSource(option)}>
            {SOURCE_LABEL[option]}
          </Chip>
        ))}
        <Chip active={unreadOnly} onClick={() => setUnreadOnly((prev) => !prev)}>
          Tylko nieprzeczytane
        </Chip>
        <div className="ml-auto">
          <MiniButton
            icon={
              <RefreshIcon
                size={13}
                className={syncMutation.isPending ? "animate-spin-ring" : ""}
              />
            }
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
          >
            {syncMutation.isPending ? "Sprawdzam…" : "Sprawdź skrzynkę"}
          </MiniButton>
        </div>
      </div>

      {showDiagnostics ? (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <MailboxDiagnostics
            onSync={() => syncMutation.mutate()}
            syncing={syncMutation.isPending}
          />
        </div>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-[300px_minmax(0,1fr)] max-[1100px]:grid-cols-1">
          <div className="min-h-0 min-w-0 overflow-y-auto border-r border-line">
            {isLoading && <SkeletonRows rows={5} />}
            {!isLoading && (data ?? []).length === 0 && (
              <EmptyState
                pose="think"
                title="Nic w tym filtrze"
                description="Zmień filtr kanału albo odznacz „tylko nieprzeczytane”."
              />
            )}
            {(data ?? []).map((message) => {
              const isSelected = selected?.message_id === message.message_id;
              return (
                <button
                  key={message.message_id}
                  onClick={() => handleSelect(message)}
                  className={`relative flex w-full flex-col gap-[5px] border-b border-line px-[18px] py-[13px] text-left transition-colors duration-150 ${
                    isSelected ? "bg-teal-dim" : "hover:bg-panel-2"
                  }`}
                >
                  {isSelected && (
                    <span className="absolute bottom-0 left-0 top-0 w-[3px] bg-teal-bright" />
                  )}
                  <span className="flex items-center gap-2">
                    {!message.is_read && (
                      <span className="h-[7px] w-[7px] shrink-0 rounded-full bg-coral" />
                    )}
                    <b className="truncate text-[12.5px] font-semibold">
                      {senderName(message.sender)}
                    </b>
                    <span className="o-mono ml-auto shrink-0 text-[9.5px] text-slate-dim">
                      {formatTime(message.received_at)}
                    </span>
                  </span>
                  <span className="truncate text-[12px] text-slate">
                    {message.subject || "(bez tematu)"}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="flex min-h-0 flex-col gap-4 overflow-y-auto px-6 py-[22px]">
            {!selected ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-2 text-slate-dim">
                <AlertIcon size={26} />
                <p className="text-[12.5px]">Wybierz wiadomość z listy, żeby zobaczyć podgląd.</p>
              </div>
            ) : (
              <>
                <h3 className="o-section-title">{selected.subject || "(bez tematu)"}</h3>
                <div className="flex items-center gap-2.5 border-b border-line pb-3.5">
                  <InitialAvatar name={senderName(selected.sender)} />
                  <div className="min-w-0">
                    <div className="truncate text-[12.5px] text-white">
                      {senderName(selected.sender)}
                    </div>
                    <div className="o-mono truncate text-[10.5px] text-slate-dim">
                      {senderAddress(selected.sender)}
                    </div>
                  </div>
                  <span className="o-mono ml-auto shrink-0 text-[10.5px] text-slate-dim">
                    {formatDateTime(selected.received_at)}
                  </span>
                </div>
                <p className="whitespace-pre-wrap text-[13px] leading-[1.72] text-slate">
                  {selected.body_preview || "(ORDLY zapisuje tylko podgląd treści)"}
                </p>
                <a
                  href={gmailSearchUrl(selected.message_id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 self-start rounded-[9px] border border-line bg-panel-2 px-3 py-2.5 text-[12px] text-slate transition-colors hover:border-line-strong hover:text-white"
                >
                  <ExternalIcon size={14} className="text-teal-bright" />
                  Otwórz pełną wiadomość w Gmail
                </a>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
