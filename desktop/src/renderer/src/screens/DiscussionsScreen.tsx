import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshIcon } from "../icons";
import { EmptyState } from "../components/EmptyState";
import type { Issue } from "../types/api";

const dateFormatter = new Intl.DateTimeFormat("pl-PL", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

/**
 * Etykiety statusow 1:1 ze schematu PostPurchaseIssueStatus w oficjalnym
 * swagger.yaml Allegro (zweryfikowane, nie zgadywane) - to jedyne 6
 * mozliwych wartosci, wiec bezpiecznie tlumaczymy i kolorujemy.
 */
const STATUS_LABEL: Record<string, string> = {
  DISPUTE_ONGOING: "W toku",
  DISPUTE_CLOSED: "Zamknięta",
  DISPUTE_UNRESOLVED: "Nierozwiązana",
  CLAIM_SUBMITTED: "Zgłoszona",
  CLAIM_ACCEPTED: "Zaakceptowana",
  CLAIM_REJECTED: "Odrzucona",
};

const STATUS_TONE: Record<string, "ok" | "warn" | "crit"> = {
  DISPUTE_ONGOING: "warn",
  DISPUTE_CLOSED: "ok",
  DISPUTE_UNRESOLVED: "crit",
  CLAIM_SUBMITTED: "warn",
  CLAIM_ACCEPTED: "ok",
  CLAIM_REJECTED: "crit",
};

const TONE_CLASS: Record<"ok" | "warn" | "crit", string> = {
  ok: "bg-success-tint text-success",
  warn: "bg-warning-tint text-warning",
  crit: "bg-danger-tint text-danger",
};

function useIssuesList() {
  return useQuery({
    queryKey: ["issues"],
    queryFn: async () => {
      const result = await window.ordly.issues.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });
}

function useIssueThread(issueId: string | null) {
  return useQuery({
    queryKey: ["issue-thread", issueId],
    enabled: issueId !== null,
    queryFn: async () => {
      const result = await window.ordly.issues.messages(issueId as string);
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });
}

function IssueThreadModal({ issue, onClose }: { issue: Issue; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { data: messages, isLoading, isError, error } = useIssueThread(issue.external_id);
  const [text, setText] = React.useState("");
  const scrollRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  const replyMutation = useMutation({
    mutationFn: async () => {
      const result = await window.ordly.issues.reply(issue.external_id, text.trim());
      if (!result.ok) throw new Error(result.message);
    },
    onSuccess: () => {
      setText("");
      void queryClient.invalidateQueries({ queryKey: ["issue-thread", issue.external_id] });
      void queryClient.invalidateQueries({ queryKey: ["issues"] });
    },
  });

  const statusTone = STATUS_TONE[issue.status] ?? "warn";

  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="flex max-h-[80vh] w-full max-w-lg flex-col rounded-2xl border border-border bg-surface"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border p-5">
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-primary-tint px-2.5 py-1 text-badge-label text-primary">
              {issue.type === "CLAIM" ? "Reklamacja" : "Dyskusja"}
            </span>
            <span className={`rounded-full px-2.5 py-1 text-badge-label ${TONE_CLASS[statusTone]}`}>
              {STATUS_LABEL[issue.status] ?? issue.status}
            </span>
          </div>
          <h2 className="mt-2 text-headline">{issue.subject ?? "Bez tematu"}</h2>
          <p className="mt-1 text-footnote text-text-secondary">
            Zamówienie {issue.order_external_id} · {issue.buyer_login}
          </p>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto p-5">
          {isLoading && <p className="text-footnote text-text-secondary">Wczytywanie wątku…</p>}
          {isError && (
            <p className="text-footnote text-danger">
              Nie udało się pobrać wątku: {error instanceof Error ? error.message : "nieznany błąd"}
            </p>
          )}
          <div className="flex flex-col gap-3">
            {messages?.map((message) => {
              const isSeller = message.author_role === "SELLER";
              return (
                <div key={message.id} className={`flex ${isSeller ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[80%] rounded-xl px-3.5 py-2.5 text-callout ${
                      isSeller ? "bg-primary-tint text-text" : "bg-surface-raised text-text"
                    }`}
                  >
                    <p>{message.text}</p>
                    <p className="mt-1 text-[10.5px] text-text-dim">
                      {isSeller ? "Ty" : message.author_login} ·{" "}
                      {dateFormatter.format(new Date(message.created_at))}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="border-t border-border p-4">
          {!issue.chat_active && (
            <p className="mb-2 text-caption text-text-dim">
              Ta dyskusja jest zamknięta - odpowiedź może się nie udać.
            </p>
          )}
          {replyMutation.isError && (
            <p className="mb-2 text-caption text-danger">
              {replyMutation.error instanceof Error
                ? replyMutation.error.message
                : "Nie udało się wysłać odpowiedzi."}
            </p>
          )}
          <div className="flex items-end gap-2">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Napisz odpowiedź…"
              rows={2}
              className="flex-1 resize-none rounded-md border border-border bg-background px-3 py-2 text-body text-text focus:border-primary focus:outline-none"
            />
            <button
              onClick={() => replyMutation.mutate()}
              disabled={text.trim().length === 0 || replyMutation.isPending}
              className="h-10 shrink-0 rounded-lg bg-gradient-to-br from-primary to-accent px-4 text-callout-semibold text-on-primary shadow-[0_8px_18px_-8px_rgba(86,224,208,0.5)] disabled:opacity-45"
            >
              {replyMutation.isPending ? "Wysyłanie…" : "Wyślij"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function DiscussionsScreen() {
  const { data, isLoading, isError, error, isFetching } = useIssuesList();
  const queryClient = useQueryClient();
  const [openIssue, setOpenIssue] = React.useState<Issue | null>(null);

  return (
    <div>
      <div className="mb-5 flex items-center justify-between gap-4">
        <h1 className="text-title1">Dyskusje</h1>
        <button
          onClick={() => void queryClient.invalidateQueries({ queryKey: ["issues"] })}
          disabled={isFetching}
          className="flex h-9 items-center gap-2 rounded-[10px] border border-border bg-surface px-3.5 text-[12.5px] font-semibold text-text-secondary hover:bg-surface-raised disabled:opacity-50"
        >
          <RefreshIcon size={14} className={isFetching ? "animate-spin" : ""} />
          Odśwież
        </button>
      </div>

      {isLoading && <p className="text-footnote text-text-secondary">Wczytywanie dyskusji…</p>}
      {isError && (
        <p className="text-footnote text-danger">
          Nie udało się pobrać dyskusji: {error instanceof Error ? error.message : "nieznany błąd"}
        </p>
      )}
      {!isLoading && !isError && data && data.length === 0 && (
        <EmptyState
          pose="happy"
          title="Brak otwartych spraw"
          description="Zero dyskusji i reklamacji do obsłużenia - spokojnie."
        />
      )}

      {data && data.length > 0 && (
        <div className="flex flex-col gap-2">
          {data.map((issue) => {
            const statusTone = STATUS_TONE[issue.status] ?? "warn";
            return (
              <button
                key={issue.external_id}
                onClick={() => setOpenIssue(issue)}
                className="flex items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3 text-left hover:bg-surface-raised"
              >
                <span className="rounded-full bg-primary-tint px-2.5 py-1 text-badge-label text-primary">
                  {issue.type === "CLAIM" ? "Reklamacja" : "Dyskusja"}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-callout-semibold">{issue.subject ?? "Bez tematu"}</p>
                  <p className="truncate text-[12px] text-text-secondary">
                    {issue.buyer_login} · zamówienie {issue.order_external_id}
                  </p>
                </div>
                <span className={`shrink-0 rounded-full px-2.5 py-1 text-badge-label ${TONE_CLASS[statusTone]}`}>
                  {STATUS_LABEL[issue.status] ?? issue.status}
                </span>
                {issue.last_message_at && (
                  <span className="shrink-0 text-[11px] tabular-nums text-text-dim">
                    {dateFormatter.format(new Date(issue.last_message_at))}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {openIssue && <IssueThreadModal issue={openIssue} onClose={() => setOpenIssue(null)} />}
    </div>
  );
}
