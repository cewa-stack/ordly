/**
 * Ordlak - asystent aplikacji.
 *
 * Uklad "lista + szczegoly" (`280px minmax(0,1fr)`), ten sam co Poczta
 * i Dyskusje: po lewej zapisane rozmowy, po prawej watek.
 *
 * Odpowiedzi liczy backend (`POST /api/v1/ordlak/chat`) - model nie
 * zgaduje liczb, tylko odczytuje je narzedziami z bazy, a lista uzytych
 * narzedzi wraca w odpowiedzi i jest pokazana pod trescia. Bez tego
 * uzytkownik nie mialby jak odroznic raportu od zmyslenia.
 *
 * Historia zyje na Pi, nie w tym komponencie - renderer wysyla POJEDYNCZE
 * pytanie plus numer watku. Dzieki temu rozmowa przezywa restart appki.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Chip, MiniButton, SkeletonRows } from "../components/ui";
import { ConfirmDialog } from "../components/Modal";
import { OrdlakMascot, type OrdlakPose } from "../components/OrdlakMascot";
import {
  AlertIcon,
  CheckIcon,
  ExportIcon,
  PlusIcon,
  RefreshIcon,
  SendIcon,
  TrashIcon,
} from "../icons";
import { useToast } from "../lib/toast";
import { formatDateTime } from "../lib/format";
import type { OrdlakConversation, OrdlakStoredMessage } from "../types/api";

/** Czytelne nazwy narzedzi backendu - klucze musza zgadzac sie z `TOOLS`. */
const TOOL_LABEL: Record<string, string> = {
  podsumowanie_sprzedazy: "sprzedaż",
  niskie_stany: "niskie stany",
  magazyn: "magazyn",
  prognoza_zapasow: "prognoza zapasów",
  ostatnie_zamowienia: "zamówienia",
  zwroty: "zwroty",
  kalendarz_sprzedazowy: "kalendarz sprzedażowy",
  szukaj: "wyszukiwarka zamówień",
  dyskusje: "dyskusje",
  watek_dyskusji: "wątek dyskusji",
  poczta: "skrzynka",
  kalkulator_ceny: "kalkulator ceny",
  stan_systemu: "stan systemu",
};

const SUGGESTIONS = [
  "Ile sprzedałem w tym tygodniu?",
  "Co ma niski stan?",
  "Jakie dni sprzedażowe się zbliżają?",
  "Mam jakieś dyskusje do odpisania?",
  "Za ile wystawić rzecz kupioną za 12 zł przy prowizji 10% i marży 30%?",
];

function ToolTrace({ tools }: { tools: string[] }) {
  const unique = [...new Set(tools)];
  if (unique.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <span className="text-[10px] text-slate-dim">na podstawie:</span>
      {unique.map((tool) => (
        <span
          key={tool}
          className="rounded-[20px] border border-line px-2 py-[2px] text-[10px] text-slate-dim"
        >
          {TOOL_LABEL[tool] ?? tool}
        </span>
      ))}
    </div>
  );
}

function AssistantBubble({
  message,
  conversationTitle,
}: {
  message: OrdlakStoredMessage;
  conversationTitle: string;
}) {
  const toast = useToast();
  const [copied, setCopied] = React.useState(false);

  async function copy() {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  async function saveToFile() {
    const result = await window.ordly.ordlak.saveReply({
      suggestedName: conversationTitle,
      content: message.content,
    });
    if (!result.ok) {
      toast.error("Nie udało się zapisać", result.message);
      return;
    }
    if (result.data.saved) {
      toast.success("Zapisano raport", result.data.path ?? "");
    }
  }

  return (
    <div className="group flex gap-2.5">
      <OrdlakMascot pose="idle" size={28} floaty={false} className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="whitespace-pre-wrap rounded-[4px_14px_14px_14px] border border-line bg-panel-2 px-3.5 py-2.5 text-[12.5px] leading-[1.7] text-white">
          {message.content}
        </p>
        <ToolTrace tools={message.used_tools} />
        {/* Akcje pojawiaja sie na hover - w spoczynku nie zasmiecaja watku,
            ale sa przy KAZDEJ odpowiedzi, nie tylko przy ostatniej. */}
        <div className="mt-1.5 flex gap-1.5 opacity-0 transition-opacity duration-150 focus-within:opacity-100 group-hover:opacity-100">
          <MiniButton
            icon={copied ? <CheckIcon size={12} /> : undefined}
            onClick={() => void copy()}
          >
            {copied ? "Skopiowano" : "Kopiuj"}
          </MiniButton>
          <MiniButton icon={<ExportIcon size={12} />} onClick={() => void saveToFile()}>
            Zapisz do pliku
          </MiniButton>
        </div>
      </div>
    </div>
  );
}

function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[78%] whitespace-pre-wrap rounded-[14px_14px_4px_14px] bg-teal-dim px-3.5 py-2.5 text-[12.5px] leading-[1.65] text-white">
        {content}
      </p>
    </div>
  );
}

export function OrdlakScreen() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [activeId, setActiveId] = React.useState<number | null>(null);
  const [draft, setDraft] = React.useState("");
  const [pendingQuestion, setPendingQuestion] = React.useState<string | null>(null);
  const [deleting, setDeleting] = React.useState<OrdlakConversation | null>(null);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  const statusQuery = useQuery({
    queryKey: ["ordlak-status"],
    queryFn: async () => {
      const result = await window.ordly.ordlak.status();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const listQuery = useQuery({
    queryKey: ["ordlak-conversations"],
    queryFn: async () => {
      const result = await window.ordly.ordlak.conversations();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const threadQuery = useQuery({
    queryKey: ["ordlak-conversation", activeId],
    enabled: activeId !== null,
    queryFn: async () => {
      const result = await window.ordly.ordlak.conversation(activeId as number);
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const askMutation = useMutation({
    mutationFn: async (message: string) => {
      const result = await window.ordly.ordlak.ask({ message, conversationId: activeId });
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (reply) => {
      setActiveId(reply.conversation_id);
      void queryClient.invalidateQueries({ queryKey: ["ordlak-conversations"] });
      void queryClient.invalidateQueries({
        queryKey: ["ordlak-conversation", reply.conversation_id],
      });
    },
    onError: (error) => {
      // Pytanie zostalo zapisane na Pi nawet przy bledzie modelu, wiec
      // odswiezamy liste - watek tam jest i mozna do niego wrocic.
      void queryClient.invalidateQueries({ queryKey: ["ordlak-conversations"] });
      if (activeId !== null) {
        void queryClient.invalidateQueries({ queryKey: ["ordlak-conversation", activeId] });
      }
      toast.error(
        "Ordlak nie odpowiedział",
        error instanceof Error ? error.message : "Spróbuj ponownie za chwilę."
      );
    },
    onSettled: () => setPendingQuestion(null),
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const result = await window.ordly.ordlak.deleteConversation(id);
      if (!result.ok) throw new Error(result.message);
      return id;
    },
    onSuccess: (id) => {
      if (activeId === id) setActiveId(null);
      setDeleting(null);
      void queryClient.invalidateQueries({ queryKey: ["ordlak-conversations"] });
      toast.success("Usunięto rozmowę", "Wątek zniknął razem z historią.");
    },
    onError: (error) => {
      toast.error(
        "Nie udało się usunąć",
        error instanceof Error ? error.message : "Spróbuj ponownie."
      );
    },
  });

  const messages = threadQuery.data?.messages ?? [];
  const conversationTitle = threadQuery.data?.title ?? "Raport Ordlaka";
  const configured = statusQuery.data?.configured ?? true;
  const canSend = draft.trim().length > 0 && !askMutation.isPending && configured;

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, pendingQuestion]);

  function send(text: string) {
    const question = text.trim();
    if (!question || askMutation.isPending) return;
    setDraft("");
    setPendingQuestion(question);
    askMutation.mutate(question);
  }

  function startNew() {
    setActiveId(null);
    setDraft("");
    askMutation.reset();
  }

  const pose: OrdlakPose = askMutation.isPending
    ? "thinking"
    : messages.length > 0
      ? "happy"
      : "idle";

  return (
    <div className="grid min-h-0 flex-1 grid-cols-[280px_minmax(0,1fr)] overflow-hidden max-[940px]:grid-cols-1">
      {/* ------------------------------------------------- lista rozmów */}
      <aside className="flex min-h-0 flex-col border-r border-line max-[940px]:hidden">
        <div className="border-b border-line px-4 py-3">
          <MiniButton
            className="w-full justify-center"
            icon={<PlusIcon size={13} />}
            onClick={startNew}
          >
            Nowa rozmowa
          </MiniButton>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
          {listQuery.isLoading && <SkeletonRows rows={4} />}
          {!listQuery.isLoading && (listQuery.data ?? []).length === 0 && (
            <p className="px-2 py-3 text-[11.5px] leading-[1.6] text-slate-dim">
              Nie masz jeszcze zapisanych rozmów. Zadaj pierwsze pytanie - wątek zapisze się
              sam i przetrwa restart aplikacji.
            </p>
          )}
          {(listQuery.data ?? []).map((conversation) => (
            <div
              key={conversation.id}
              className={`group mb-1 flex items-center gap-2 rounded-[9px] px-2.5 py-2 transition-colors duration-150 ${
                conversation.id === activeId ? "bg-panel-3" : "hover:bg-panel-2"
              }`}
            >
              <button
                onClick={() => setActiveId(conversation.id)}
                className="min-w-0 flex-1 text-left"
              >
                <span
                  className={`block truncate text-[12px] ${
                    conversation.id === activeId ? "text-white" : "text-slate"
                  }`}
                >
                  {conversation.title}
                </span>
                <span className="o-mono block text-[10px] text-slate-dim">
                  {formatDateTime(conversation.updated_at)} · {conversation.message_count}{" "}
                  wiadomości
                </span>
              </button>
              <button
                onClick={() => setDeleting(conversation)}
                aria-label={`Usuń rozmowę ${conversation.title}`}
                className="shrink-0 rounded-md p-1 text-slate-dim opacity-0 transition-all duration-150 hover:bg-panel-3 hover:text-coral group-hover:opacity-100"
              >
                <TrashIcon size={13} />
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* ------------------------------------------------------- rozmowa */}
      <section className="flex min-h-0 flex-col">
        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-5 py-[18px]">
          <div className="mx-auto flex w-full max-w-[760px] flex-col gap-3.5">
            {!configured && (
              <div className="flex items-start gap-2.5 rounded-[9px] border border-[rgba(255,133,99,.3)] bg-[rgba(255,133,99,.08)] px-3.5 py-3">
                <AlertIcon size={15} className="mt-0.5 shrink-0 text-coral" />
                <p className="text-[11.5px] leading-[1.6] text-slate">
                  Ordlak nie ma klucza API, więc nie odpowie. Uzupełnij{" "}
                  <code className="o-mono text-slate">ANTHROPIC_API_KEY</code> w{" "}
                  <code className="o-mono text-slate">~/ordly/backend/.env</code> na Pi i
                  zrestartuj usługę:{" "}
                  <code className="o-mono text-slate">sudo systemctl restart ordly</code>.
                </p>
              </div>
            )}

            {activeId === null && !pendingQuestion && (
              <div className="flex flex-col items-center gap-3 py-10 text-center">
                <OrdlakMascot pose={pose} size={92} />
                <h3 className="o-card-title">Zapytaj o swój sklep</h3>
                <p className="max-w-[460px] text-[12px] leading-[1.7] text-slate-dim">
                  Ordlak czyta te same dane co reszta aplikacji - sprzedaż, magazyn, zwroty,
                  dyskusje, skrzynkę i kalendarz sprzedażowy. Liczby bierze z bazy, nie
                  z pamięci, a cenę liczy wzorem, nie na oko.
                </p>
                <div className="mt-1 flex flex-wrap justify-center gap-2">
                  {SUGGESTIONS.map((suggestion) => (
                    <Chip
                      key={suggestion}
                      onClick={() => send(suggestion)}
                      disabled={!configured}
                    >
                      {suggestion}
                    </Chip>
                  ))}
                </div>
              </div>
            )}

            {threadQuery.isLoading && activeId !== null && <SkeletonRows rows={3} />}

            {messages.map((message, index) =>
              message.role === "user" ? (
                <UserBubble key={index} content={message.content} />
              ) : (
                <AssistantBubble
                  key={index}
                  message={message}
                  conversationTitle={conversationTitle}
                />
              )
            )}

            {pendingQuestion && <UserBubble content={pendingQuestion} />}

            {askMutation.isPending && (
              <div className="flex items-center gap-2.5">
                <OrdlakMascot pose="thinking" size={28} floaty={false} className="shrink-0" />
                <span className="o-mono animate-pulse text-[11px] text-slate-dim">
                  Ordlak sprawdza dane…
                </span>
              </div>
            )}

            {askMutation.isError && !askMutation.isPending && (
              <div className="flex items-center gap-2 pl-[38px]">
                <span className="text-[11.5px] text-coral">Odpowiedź nie doszła.</span>
                <MiniButton
                  icon={<RefreshIcon size={13} />}
                  onClick={() => {
                    const lastQuestion = [...messages]
                      .reverse()
                      .find((message) => message.role === "user");
                    if (lastQuestion) send(lastQuestion.content);
                    else toast.error("Nie ma czego ponowić", "Zadaj pytanie jeszcze raz.");
                  }}
                >
                  Ponów
                </MiniButton>
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-line px-5 py-3">
          <div className="mx-auto flex w-full max-w-[760px] flex-col gap-2">
            <div className="flex items-end gap-2">
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  // Enter wysyla, Shift+Enter robi nowa linie - jak w kazdym
                  // czacie. Bez tego dluzsze pytanie wymagaloby myszki.
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    send(draft);
                  }
                }}
                rows={1}
                disabled={!configured}
                placeholder={
                  configured
                    ? "Zapytaj o sprzedaż, magazyn, dyskusje albo cenę oferty…"
                    : "Brak klucza API na Pi - asystent jest wyłączony."
                }
                className="max-h-[140px] min-h-[42px] w-full resize-y rounded-[10px] border border-line bg-panel-2 px-3.5 py-2.5 text-[12.5px] leading-[1.6] text-white outline-none transition-colors focus:border-teal-bright disabled:opacity-50"
              />
              <button
                onClick={() => send(draft)}
                disabled={!canSend}
                aria-label="Wyślij pytanie"
                className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-[10px] bg-teal-bright text-[#052321] transition-[transform,filter] duration-150 ease-ordly hover:brightness-110 active:scale-[.985] disabled:pointer-events-none disabled:opacity-40"
              >
                <SendIcon size={16} />
              </button>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-[10.5px] text-slate-dim">
                Enter wysyła, Shift+Enter to nowa linia. Rozmowy zapisują się na Pi.
              </span>
              {activeId !== null && (
                <MiniButton
                  className="ml-auto"
                  icon={<PlusIcon size={13} />}
                  onClick={startNew}
                  disabled={askMutation.isPending}
                >
                  Nowa rozmowa
                </MiniButton>
              )}
            </div>
          </div>
        </div>
      </section>

      <ConfirmDialog
        open={deleting !== null}
        title={`Usunąć rozmowę „${deleting?.title ?? ""}"?`}
        message="Wątek zniknie razem z całą historią pytań i odpowiedzi. Tego nie da się cofnąć."
        confirmLabel="Usuń rozmowę"
        pending={deleteMutation.isPending}
        onConfirm={() => deleting && deleteMutation.mutate(deleting.id)}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}
