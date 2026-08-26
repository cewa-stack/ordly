/**
 * Dyskusje - uklad "lista + rozmowa" (`1fr 330px`, sekcja 4.3).
 *
 * Panel to dymki rozmowy: `them` po lewej (`--panel-2`), `me` po prawej
 * (`--teal-dim`), plus pole odpowiedzi z szablonami. Szablony realnie
 * wstawiaja tresc do pola (sekcja 9.1 pkt 10) - wczesniej ikona
 * szablonu nie robila nic.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SendIcon, TemplateIcon } from "../icons";
import {
  Button,
  EmptyState,
  ErrorState,
  IconButton,
  InitialAvatar,
  MarketplaceBadge,
  Pill,
  SkeletonRows,
  type PillTone,
} from "../components/ui";
import { useToast } from "../lib/toast";
import { formatAge, formatDateTime } from "../lib/format";
import { htmlToPlainText, looksLikeHtml, sanitizeMessageHtml } from "../lib/sanitizeHtml";
import type { Issue } from "../types/api";

/**
 * Etykiety statusow 1:1 ze schematu PostPurchaseIssueStatus w oficjalnym
 * swagger.yaml Allegro (zweryfikowane, nie zgadywane) - to jedyne 6
 * mozliwych wartosci.
 */
const STATUS_LABEL: Record<string, string> = {
  DISPUTE_ONGOING: "W toku",
  DISPUTE_CLOSED: "Zamknięta",
  DISPUTE_UNRESOLVED: "Nierozwiązana",
  CLAIM_SUBMITTED: "Zgłoszona",
  CLAIM_ACCEPTED: "Zaakceptowana",
  CLAIM_REJECTED: "Odrzucona",
};

const STATUS_TONE: Record<string, PillTone> = {
  DISPUTE_ONGOING: "pack",
  DISPUTE_CLOSED: "done",
  DISPUTE_UNRESOLVED: "warn",
  CLAIM_SUBMITTED: "pack",
  CLAIM_ACCEPTED: "new",
  CLAIM_REJECTED: "warn",
};

/** Szablony odpowiedzi - tresc wg regul tonu z sekcji 7.1: konkret, bez sprytu. */
const TEMPLATES: { name: string; text: string }[] = [
  {
    name: "Potwierdzenie zgłoszenia",
    text: "Dzień dobry,\n\ndziękuję za zgłoszenie. Sprawdzam sprawę i wracam z odpowiedzią najpóźniej jutro do południa.\n\nPozdrawiam",
  },
  {
    name: "Wysyłka w toku",
    text: "Dzień dobry,\n\npaczka jest już spakowana i trafi do kuriera dzisiaj. Numer przesyłki wyślę, gdy tylko go otrzymam.\n\nPozdrawiam",
  },
  {
    name: "Prośba o zdjęcia",
    text: "Dzień dobry,\n\nżeby szybciej rozwiązać sprawę, proszę o 2-3 zdjęcia produktu i opakowania. Na tej podstawie od razu zaproponuję rozwiązanie.\n\nPozdrawiam",
  },
  {
    name: "Zwrot przyjęty",
    text: "Dzień dobry,\n\nzwrot przyjęty. Zwrot środków uruchamiam po odbiorze przesyłki - księgowanie zajmuje zwykle 2-3 dni robocze.\n\nPozdrawiam",
  },
];

/**
 * Tresc jednej wiadomosci w watku.
 *
 * Komunikaty systemowe Allegro ("Dyskusja trwa juz 14 dni...") przychodza
 * jako HTML, wiec renderowane jako zwykly tekst pokazywaly uzytkownikowi
 * doslowne `<br>` i `<strong>`. Wiadomosci wpisane przez czlowieka to z
 * kolei czysty tekst ze znakami nowej linii - dla nich zostaje
 * `whitespace-pre-wrap`, bo przepuszczenie ich przez parser HTML
 * zjadloby te znaki.
 */
function MessageBody({ text }: { text: string }) {
  const html = React.useMemo(
    () => (looksLikeHtml(text) ? sanitizeMessageHtml(text) : null),
    [text]
  );

  if (!text.trim()) {
    return <p className="whitespace-pre-wrap">(wiadomość bez treści)</p>;
  }
  if (html === null) {
    return <p className="whitespace-pre-wrap">{text}</p>;
  }
  return <div className="o-html-preview" dangerouslySetInnerHTML={{ __html: html }} />;
}

/**
 * Dwuliniowy podglad watku na liscie - zawsze czysty tekst.
 *
 * Opis dyskusji potrafi przyjsc z Allegro z tymi samymi znacznikami co
 * tresc wiadomosci, a `<br>` w podgladzie wyglada jak blad aplikacji.
 */
function issuePreview(issue: Issue): string {
  const raw = issue.description ?? issue.subject ?? "";
  const text = looksLikeHtml(raw) ? htmlToPlainText(raw) : raw;
  return text.trim() || "Bez treści";
}

function useIssues() {
  return useQuery({
    queryKey: ["issues"],
    queryFn: async () => {
      const result = await window.ordly.issues.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    retry: false,
  });
}

function Conversation({ issue }: { issue: Issue }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [text, setText] = React.useState("");
  const [templatesOpen, setTemplatesOpen] = React.useState(false);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  const threadQuery = useQuery({
    queryKey: ["issue-thread", issue.external_id],
    queryFn: async () => {
      const result = await window.ordly.issues.messages(issue.external_id);
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    retry: false,
  });

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [threadQuery.data]);

  const replyMutation = useMutation({
    mutationFn: async () => {
      const result = await window.ordly.issues.reply(issue.external_id, text.trim());
      if (!result.ok) throw new Error(result.message);
    },
    onSuccess: () => {
      setText("");
      void queryClient.invalidateQueries({ queryKey: ["issue-thread", issue.external_id] });
      void queryClient.invalidateQueries({ queryKey: ["issues"] });
      toast.success("Odpowiedź wysłana", `Do ${issue.buyer_login}`);
    },
    onError: (error) => {
      toast.error(
        "Allegro nie przyjęło odpowiedzi",
        error instanceof Error ? error.message : "Spróbuj ponownie za chwilę."
      );
    },
  });

  return (
    <div className="flex min-h-0 flex-col gap-3.5 overflow-hidden border-l border-line p-5">
      <div className="flex shrink-0 flex-col gap-1">
        <div className="flex items-center gap-2">
          <MarketplaceBadge marketplace={issue.marketplace} />
          <Pill tone={STATUS_TONE[issue.status] ?? "warn"}>
            {STATUS_LABEL[issue.status] ?? issue.status}
          </Pill>
        </div>
        <h3 className="o-section-title mt-1">{issue.subject ?? "Bez tematu"}</h3>
        <p className="o-mono text-[11px] text-slate-dim">
          {issue.buyer_login} · {issue.messages_count} wiadomości
        </p>
      </div>

      <div ref={scrollRef} className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
        {threadQuery.isLoading && (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 3 }).map((_, index) => (
              <span key={index} className="o-skeleton-bar h-12 w-[80%]" />
            ))}
          </div>
        )}
        {threadQuery.isError && (
          <p className="text-[12px] leading-relaxed text-coral">
            Allegro nie zwróciło treści tego wątku.{" "}
            {threadQuery.error instanceof Error ? threadQuery.error.message : ""}
          </p>
        )}
        {threadQuery.data?.map((message) => {
          const isSeller = message.author_role === "SELLER";
          return (
            <div
              key={`${message.id}-${message.created_at}`}
              className={`max-w-[85%] rounded-md px-3.5 py-3 text-[12.5px] leading-[1.55] ${
                isSeller
                  ? "self-end rounded-tr-[4px] bg-teal-dim text-white"
                  : "rounded-tl-[4px] bg-panel-2 text-white"
              }`}
            >
              <MessageBody text={message.text} />
              <span className="o-mono mt-1.5 block text-[9.5px] text-slate-dim">
                {isSeller ? "Ty" : message.author_login} ·{" "}
                {formatDateTime(message.created_at)}
              </span>
            </div>
          );
        })}
      </div>

      <div className="relative shrink-0">
        {templatesOpen && (
          <div className="absolute bottom-full left-0 right-0 z-10 mb-2 overflow-hidden rounded-md border border-line-strong bg-panel shadow-palette">
            {TEMPLATES.map((template) => (
              <button
                key={template.name}
                onClick={() => {
                  setText(template.text);
                  setTemplatesOpen(false);
                }}
                className="block w-full border-b border-line px-3.5 py-2.5 text-left text-[12px] text-slate last:border-b-0 hover:bg-panel-2 hover:text-white"
              >
                {template.name}
              </button>
            ))}
          </div>
        )}

        <div className="flex flex-col gap-2.5 rounded-md border border-line-strong bg-panel-2 px-3 py-3">
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Napisz odpowiedź…"
            rows={3}
            disabled={!issue.chat_active}
            className="resize-none bg-transparent text-[12.5px] leading-[1.55] text-white outline-none placeholder:text-slate-dim disabled:opacity-50"
          />
          <div className="flex items-center gap-2">
            <IconButton
              onClick={() => setTemplatesOpen((prev) => !prev)}
              aria-label="Wstaw szablon odpowiedzi"
              title="Szablony odpowiedzi"
            >
              <TemplateIcon size={14} />
            </IconButton>
            {!issue.chat_active && (
              <span className="text-[10.5px] text-slate-dim">
                Wątek zamknięty przez Allegro
              </span>
            )}
            <Button
              className="ml-auto !px-3.5 !py-[7px] !text-[12px]"
              onClick={() => replyMutation.mutate()}
              disabled={
                !issue.chat_active || text.trim().length === 0 || replyMutation.isPending
              }
              icon={<SendIcon size={13} />}
            >
              {replyMutation.isPending ? "Wysyłam…" : "Wyślij"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function DiscussionsScreen() {
  const { data, isLoading, isError, error, refetch } = useIssues();
  const [selectedId, setSelectedId] = React.useState<string | null>(null);

  const selected =
    (data ?? []).find((issue) => issue.external_id === selectedId) ?? (data ?? [])[0];

  if (isError) {
    return (
      <ErrorState
        title="Nie udało się pobrać dyskusji"
        detail={`${
          error instanceof Error ? error.message : "Nieznany błąd."
        } Jeśli w treści jest 403 AccessDenied, brakuje uprawnienia "Dyskusje i reklamacje pozakupowe" w rejestracji aplikacji na apps.developer.allegro.pl.`}
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_330px] max-[1100px]:grid-cols-1">
      <div className="min-h-0 min-w-0 overflow-y-auto">
        {isLoading && <SkeletonRows rows={5} />}
        {!isLoading && (data ?? []).length === 0 && (
          <EmptyState
            pose="happy"
            title="Brak otwartych spraw"
            description="Zero dyskusji i reklamacji do obsłużenia - spokojnie."
          />
        )}
        {(data ?? []).map((issue) => {
          const isSelected = selected?.external_id === issue.external_id;
          return (
            <button
              key={issue.external_id}
              onClick={() => setSelectedId(issue.external_id)}
              className={`relative flex w-full items-start gap-3 border-b border-line px-[22px] py-[15px] text-left transition-colors duration-150 ease-ordly ${
                isSelected ? "bg-teal-dim" : "hover:bg-panel-2"
              }`}
            >
              {isSelected && (
                <span className="absolute bottom-0 left-0 top-0 w-[3px] bg-teal-bright" />
              )}
              <InitialAvatar name={issue.buyer_login} />
              <span className="min-w-0 flex-1">
                <span className="mb-1 flex items-center gap-2.5">
                  <span className="text-[13px] font-semibold">{issue.buyer_login}</span>
                  <MarketplaceBadge marketplace={issue.marketplace} />
                  <span className="o-mono ml-auto text-[10px] text-slate-dim">
                    {issue.last_message_at ? formatAge(issue.last_message_at) : "—"}
                  </span>
                </span>
                <span className="line-clamp-2 block text-[12.5px] leading-[1.5] text-slate">
                  {issuePreview(issue)}
                </span>
              </span>
              {issue.chat_active && (
                <span className="mt-1.5 h-[7px] w-[7px] shrink-0 rounded-full bg-coral" />
              )}
            </button>
          );
        })}
      </div>

      {selected ? (
        <Conversation key={selected.external_id} issue={selected} />
      ) : (
        <div className="flex items-center justify-center border-l border-line p-5 text-center text-[12.5px] text-slate-dim">
          Wybierz wątek z listy, żeby zobaczyć rozmowę.
        </div>
      )}
    </div>
  );
}
