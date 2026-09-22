/**
 * Ustawienia -> Szablony odpowiedzi.
 *
 * Jedyne miejsce, w ktorym szablony sie zmienia. Pole odpowiedzi w
 * Dyskusjach (desktop i telefon) tylko je wstawia - dzieki temu na
 * telefonie nie ma edytora, ktory na malym ekranie bylby udreka.
 *
 * Znaczniki wstawia sie przyciskami, nie z pamieci: literowka w
 * `{numer_przesylki}` przeszlaby do kupujacego doslownie.
 */
import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, MiniButton } from "./ui";
import { ConfirmDialog, Modal } from "./Modal";
import { useToast } from "../lib/toast";
import { TEMPLATE_TOKENS, useReplyTemplates } from "../lib/replyTemplate";
import type { ReplyTemplate } from "../types/api";

const inputClass =
  "w-full rounded-sm border border-line bg-base px-3 py-2.5 text-[12.5px] text-text outline-none focus:border-teal";

type Draft = { id: number | null; title: string; body: string };

function TemplateEditor({
  draft,
  onClose,
}: {
  draft: Draft;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [title, setTitle] = React.useState(draft.title);
  const [body, setBody] = React.useState(draft.body);
  const bodyRef = React.useRef<HTMLTextAreaElement>(null);

  const save = useMutation({
    mutationFn: async () => {
      const input = { title: title.trim(), body: body.trim() };
      const result =
        draft.id === null
          ? await window.ordly.templates.create(input)
          : await window.ordly.templates.update(draft.id, input);
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ["reply-templates"] });
      toast.success(draft.id === null ? "Szablon dodany" : "Szablon zapisany", saved.title);
      onClose();
    },
    onError: (error) => {
      toast.error(
        "Nie udało się zapisać szablonu",
        error instanceof Error ? error.message : "Spróbuj ponownie za chwilę."
      );
    },
  });

  /** Wstawia znacznik w miejscu kursora, a nie na koncu tekstu. */
  function insertToken(token: string) {
    const area = bodyRef.current;
    if (!area) {
      setBody((prev) => prev + token);
      return;
    }
    const start = area.selectionStart;
    const end = area.selectionEnd;
    const next = body.slice(0, start) + token + body.slice(end);
    setBody(next);
    requestAnimationFrame(() => {
      area.focus();
      area.setSelectionRange(start + token.length, start + token.length);
    });
  }

  const canSave = title.trim().length > 0 && body.trim().length > 0 && !save.isPending;

  return (
    <Modal
      open
      onClose={onClose}
      title={draft.id === null ? "Nowy szablon" : "Edycja szablonu"}
      subtitle="Ten sam szablon zobaczysz na telefonie"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={save.isPending}>
            Anuluj
          </Button>
          <Button onClick={() => save.mutate()} disabled={!canSave}>
            {save.isPending ? "Zapisuję…" : "Zapisz"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <label className="flex flex-col gap-1.5">
          <span className="o-eyebrow">Nazwa na liście</span>
          <input
            value={title}
            maxLength={80}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="np. Wysłane — numer przesyłki"
            className={inputClass}
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="o-eyebrow">Treść</span>
          <textarea
            ref={bodyRef}
            value={body}
            rows={8}
            onChange={(event) => setBody(event.target.value)}
            className={`${inputClass} resize-y leading-[1.55]`}
          />
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11.5px] text-text-3">Wstaw:</span>
          {TEMPLATE_TOKENS.map(({ token, label }) => (
            <MiniButton key={token} onClick={() => insertToken(token)} title={token}>
              {label}
            </MiniButton>
          ))}
        </div>
        <p className="text-[11.5px] leading-[1.5] text-text-3">
          Przy wstawianiu aplikacja podstawi dane z wątku. Gdy zamówienie nie ma jeszcze numeru
          przesyłki, w tekście zostanie luka do uzupełnienia — bez tego odpowiedź się nie wyśle.
        </p>
      </div>
    </Modal>
  );
}

export function ReplyTemplatesSettings() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const templatesQuery = useReplyTemplates();
  const [draft, setDraft] = React.useState<Draft | null>(null);
  const [toDelete, setToDelete] = React.useState<ReplyTemplate | null>(null);

  const remove = useMutation({
    mutationFn: async (template: ReplyTemplate) => {
      const result = await window.ordly.templates.delete(template.id);
      if (!result.ok) throw new Error(result.message);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reply-templates"] });
      toast.success("Szablon usunięty", toDelete?.title);
      setToDelete(null);
    },
    onError: (error) => {
      toast.error(
        "Nie udało się usunąć szablonu",
        error instanceof Error ? error.message : "Spróbuj ponownie za chwilę."
      );
    },
  });

  return (
    <div className="flex flex-col gap-2">
      {templatesQuery.isError && (
        <p className="rounded-md border border-line bg-panel-2 px-[17px] py-[15px] text-[12px] leading-relaxed text-coral">
          Nie udało się pobrać szablonów.{" "}
          {templatesQuery.error instanceof Error ? templatesQuery.error.message : ""}
        </p>
      )}
      {templatesQuery.data?.map((template) => (
        <div
          key={template.id}
          className="flex items-center gap-4 rounded-md border border-line bg-panel-2 px-[17px] py-[13px]"
        >
          <div className="min-w-0 flex-1">
            <h4 className="mb-[3px] text-[13px] font-semibold">{template.title}</h4>
            <p className="line-clamp-1 text-[11.5px] leading-[1.45] text-text-3">
              {template.body.replace(/\s+/g, " ")}
            </p>
          </div>
          <MiniButton
            onClick={() => setDraft({ id: template.id, title: template.title, body: template.body })}
          >
            Edytuj
          </MiniButton>
          <MiniButton onClick={() => setToDelete(template)} className="hover:!text-coral">
            Usuń
          </MiniButton>
        </div>
      ))}
      <div>
        <MiniButton onClick={() => setDraft({ id: null, title: "", body: "" })}>
          + Dodaj szablon
        </MiniButton>
      </div>

      {draft && <TemplateEditor draft={draft} onClose={() => setDraft(null)} />}

      <ConfirmDialog
        open={toDelete !== null}
        title="Usunąć szablon?"
        message={`„${toDelete?.title ?? ""}” zniknie z listy na desktopie i na telefonie.`}
        confirmLabel="Usuń"
        pending={remove.isPending}
        onConfirm={() => toDelete && remove.mutate(toDelete)}
        onClose={() => setToDelete(null)}
      />
    </div>
  );
}
