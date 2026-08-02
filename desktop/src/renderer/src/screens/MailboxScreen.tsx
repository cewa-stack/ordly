import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MailIcon, RefreshIcon } from "../icons";
import { EmptyState } from "../components/EmptyState";
import type { MailMessage } from "../types/api";

const dateFormatter = new Intl.DateTimeFormat("pl-PL", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

type SourceFilter = "all" | "allegro" | "olx";

const SOURCE_LABEL: Record<string, string> = {
  allegro: "Allegro",
  olx: "OLX",
  other: "Inne",
};

function gmailSearchUrl(messageId: string): string {
  const cleaned = messageId.replace(/[<>]/g, "");
  return `https://mail.google.com/mail/u/0/#search/rfc822msgid:${encodeURIComponent(cleaned)}`;
}

function useMailboxList(source: SourceFilter, unreadOnly: boolean) {
  return useQuery({
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
}

export function MailboxScreen() {
  const [source, setSource] = React.useState<SourceFilter>("all");
  const [unreadOnly, setUnreadOnly] = React.useState(false);
  const [selected, setSelected] = React.useState<MailMessage | null>(null);
  const { data, isLoading, isError, error, isFetching } = useMailboxList(source, unreadOnly);
  const queryClient = useQueryClient();

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
    setSelected(message);
    if (!message.is_read) {
      markReadMutation.mutate(message.message_id);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h1 className="text-title1">Skrzynka</h1>
        <button
          onClick={() => void queryClient.invalidateQueries({ queryKey: ["mailbox"] })}
          disabled={isFetching}
          className="flex h-9 items-center gap-2 rounded-[10px] border border-border bg-surface px-3.5 text-[12.5px] font-semibold text-text-secondary hover:bg-surface-raised disabled:opacity-50"
        >
          <RefreshIcon size={14} className={isFetching ? "animate-spin" : ""} />
          Odśwież
        </button>
      </div>

      <div className="mb-4 flex items-center gap-2">
        {(["all", "allegro", "olx"] as const).map((option) => (
          <button
            key={option}
            onClick={() => setSource(option)}
            className={`rounded-full px-3 py-1.5 text-[12.5px] font-semibold ${
              source === option
                ? "bg-primary-tint text-primary"
                : "border border-border text-text-secondary hover:bg-surface-raised"
            }`}
          >
            {option === "all" ? "Wszystkie" : SOURCE_LABEL[option]}
          </button>
        ))}
        <label className="ml-2 flex items-center gap-1.5 text-[12.5px] text-text-secondary">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => setUnreadOnly(e.target.checked)}
          />
          Tylko nieprzeczytane
        </label>
      </div>

      {isLoading && <p className="text-footnote text-text-secondary">Wczytywanie skrzynki…</p>}
      {isError && (
        <p className="text-footnote text-danger">
          Nie udało się pobrać skrzynki: {error instanceof Error ? error.message : "nieznany błąd"}
        </p>
      )}
      {!isLoading && !isError && data && data.length === 0 && (
        <EmptyState
          pose="happy"
          title="Brak maili do pokazania"
          description="Nowe wiadomości od Allegro i OLX pojawią się tutaj automatycznie."
        />
      )}

      {data && data.length > 0 && (
        <div className="flex min-h-0 flex-1 gap-4">
          <div className="w-[340px] shrink-0 overflow-y-auto rounded-xl border border-border bg-surface">
            {data.map((message, index) => {
              const isSelected = selected?.message_id === message.message_id;
              const isLast = index === data.length - 1;
              return (
                <button
                  key={message.message_id}
                  onClick={() => handleSelect(message)}
                  className={`flex w-full flex-col gap-1 px-4 py-3 text-left ${
                    isLast ? "" : "border-b border-border"
                  } ${isSelected ? "bg-primary-tint" : "hover:bg-surface-raised"}`}
                >
                  <div className="flex items-center gap-2">
                    {!message.is_read && (
                      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                    )}
                    <span
                      className={`truncate text-[12.5px] ${
                        message.is_read ? "text-text-secondary" : "font-semibold text-text"
                      }`}
                    >
                      {message.sender}
                    </span>
                    <span className="ml-auto shrink-0 rounded-full bg-surface-raised px-2 py-0.5 text-[9.5px] font-semibold uppercase text-text-dim">
                      {SOURCE_LABEL[message.source] ?? message.source}
                    </span>
                  </div>
                  <p
                    className={`truncate text-[13px] ${
                      message.is_read ? "text-text-secondary" : "font-semibold text-text"
                    }`}
                  >
                    {message.subject || "(bez tematu)"}
                  </p>
                  <p className="text-[11px] tabular-nums text-text-dim">
                    {dateFormatter.format(new Date(message.received_at))}
                  </p>
                </button>
              );
            })}
          </div>

          <div className="min-w-0 flex-1 overflow-y-auto rounded-xl border border-border bg-surface p-6">
            {!selected ? (
              <div className="flex h-full flex-col items-center justify-center gap-2 text-text-dim">
                <MailIcon size={28} />
                <p className="text-footnote">Wybierz mail z listy, żeby zobaczyć podgląd.</p>
              </div>
            ) : (
              <div>
                <p className="text-[12px] text-text-secondary">{selected.sender}</p>
                <h2 className="mt-1 text-headline">{selected.subject || "(bez tematu)"}</h2>
                <p className="mt-1 text-[12px] tabular-nums text-text-dim">
                  {dateFormatter.format(new Date(selected.received_at))}
                </p>
                <p className="mt-4 whitespace-pre-wrap text-body text-text-secondary">
                  {selected.body_preview}
                </p>
                <a
                  href={gmailSearchUrl(selected.message_id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-4 inline-block text-[12.5px] font-semibold text-primary hover:underline"
                >
                  Otwórz pełną wiadomość w Gmail →
                </a>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
