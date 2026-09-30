/**
 * Ustawienia -> Szablony maili do hurtowni.
 *
 * Jedyne miejsce, w ktorym szablony sie zmienia. Hurtownia ma tylko
 * wybor szablonu (edycja hurtowni), a okno "Napisz zamówienie" sklada
 * z niego gotowy mail, ktory i tak mozna poprawic przed wyslaniem.
 *
 * Szablon domyslny obsluguje hurtownie bez przypisania, wiec nie da sie
 * go usunac - najpierw trzeba wskazac inny jako domyslny.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, MiniButton } from "./ui";
import { ConfirmDialog, Modal } from "./Modal";
import { useToast } from "../lib/toast";
import {
  WHOLESALER_TEMPLATE_TOKENS,
  findTemplateWarnings,
  renderWholesalerEmail,
  useWholesalerTemplates,
} from "../lib/wholesalerTemplate";
import type { WholesalerTemplate, WholesalerTemplateInput } from "../types/api";

const inputClass =
  "w-full rounded-sm border border-line bg-base px-3 py-2.5 text-[12.5px] text-text outline-none focus:border-teal";

type Variant = "order" | "inquiry";
type Field = "subject" | "body";

/** Dane tylko do podgladu w edytorze - nigdzie nie sa wysylane. */
const PREVIEW_RECIPIENT = { name: "Hurtownia Przykładowa", contactPerson: "Pani Anno" };
const PREVIEW_ITEMS = [
  { name: "Wosk sojowy 1 kg", quantity: 5 },
  { name: "Słoik szklany 220 ml", quantity: 40 },
];

/** Ipc zwraca blad jako "Error invoking remote method '...': Error: <tresc>". */
function errorMessage(error: unknown): string {
  if (!(error instanceof Error)) return "Spróbuj ponownie za chwilę.";
  return error.message.replace(/^Error invoking remote method '[^']*': (Error: )?/, "");
}

function TemplateEditor({
  draft,
  onClose,
}: {
  draft: WholesalerTemplateInput;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [values, setValues] = React.useState(draft);
  const [variant, setVariant] = React.useState<Variant>("order");
  const lastFocused = React.useRef<Field>("body");
  const subjectRef = React.useRef<HTMLInputElement>(null);
  const bodyRef = React.useRef<HTMLTextAreaElement>(null);

  const subjectKey = variant === "order" ? "subject" : "inquirySubject";
  const bodyKey = variant === "order" ? "body" : "inquiryBody";

  const save = useMutation({
    mutationFn: () =>
      window.ordly.wholesalers.saveTemplate({ ...values, name: values.name.trim() }),
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ["wholesaler-templates"] });
      toast.success(draft.id ? "Szablon zapisany" : "Szablon dodany", saved.name);
      onClose();
    },
    onError: (error) => toast.error("Nie udało się zapisać szablonu", errorMessage(error)),
  });

  /** Wstawia znacznik w miejscu kursora ostatnio uzywanego pola. */
  function insertToken(token: string) {
    const key = lastFocused.current === "subject" ? subjectKey : bodyKey;
    const element = lastFocused.current === "subject" ? subjectRef.current : bodyRef.current;
    const current = values[key];
    const start = element?.selectionStart ?? current.length;
    const end = element?.selectionEnd ?? current.length;
    setValues((prev) => ({ ...prev, [key]: current.slice(0, start) + token + current.slice(end) }));
    requestAnimationFrame(() => {
      element?.focus();
      element?.setSelectionRange(start + token.length, start + token.length);
    });
  }

  const warnings = findTemplateWarnings(values);
  const preview = renderWholesalerEmail(
    { ...values, id: "", isDefault: false },
    PREVIEW_RECIPIENT,
    variant === "order" ? PREVIEW_ITEMS : []
  );

  const canSave =
    values.name.trim().length > 0 &&
    values.subject.trim().length > 0 &&
    values.body.trim().length > 0 &&
    values.inquirySubject.trim().length > 0 &&
    values.inquiryBody.trim().length > 0 &&
    !save.isPending;

  return (
    <Modal
      open
      onClose={onClose}
      title={draft.id ? "Edycja szablonu" : "Nowy szablon"}
      subtitle="Mail do hurtowni - przed wysłaniem i tak możesz go poprawić"
      width={620}
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
          <span className="o-eyebrow">Nazwa szablonu</span>
          <input
            value={values.name}
            maxLength={80}
            onChange={(event) => setValues((prev) => ({ ...prev, name: event.target.value }))}
            placeholder="np. Zamówienie - hurtownia opakowań"
            className={inputClass}
          />
        </label>

        <div className="flex gap-1 self-start rounded-pill border border-line p-[3px]">
          {(
            [
              ["order", "Zamówienie"],
              ["inquiry", "Zapytanie (bez pozycji)"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setVariant(key)}
              aria-pressed={variant === key}
              className={`rounded-pill px-3 py-[5px] text-[11.5px] transition-colors ${
                variant === key ? "bg-panel-3 text-text" : "text-text-3 hover:text-text"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <p className="-mt-1.5 text-[11.5px] leading-[1.5] text-text-3">
          {variant === "order"
            ? "Idzie, gdy w mailu są zaznaczone pozycje."
            : "Idzie, gdy nie zaznaczysz żadnej pozycji - pytanie o cennik, termin, nowy produkt."}
        </p>

        <label className="flex flex-col gap-1.5">
          <span className="o-eyebrow">Temat</span>
          <input
            ref={subjectRef}
            value={values[subjectKey]}
            onFocus={() => (lastFocused.current = "subject")}
            onChange={(event) =>
              setValues((prev) => ({ ...prev, [subjectKey]: event.target.value }))
            }
            className={inputClass}
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="o-eyebrow">Treść</span>
          <textarea
            ref={bodyRef}
            value={values[bodyKey]}
            rows={9}
            onFocus={() => (lastFocused.current = "body")}
            onChange={(event) => setValues((prev) => ({ ...prev, [bodyKey]: event.target.value }))}
            className={`${inputClass} resize-y leading-[1.55]`}
          />
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11.5px] text-text-3">Wstaw:</span>
          {WHOLESALER_TEMPLATE_TOKENS.map(({ token, label }) => (
            <MiniButton key={token} onClick={() => insertToken(token)} title={token}>
              {label}
            </MiniButton>
          ))}
        </div>
        <p className="text-[11.5px] leading-[1.5] text-text-3">
          Gdy hurtownia nie ma osoby kontaktowej, znacznik znika razem ze spacją przed nim.
          „Produkty w skrócie” to nazwa jedynej pozycji albo „kilka produktów”.
        </p>

        {warnings.length > 0 && (
          <div className="flex flex-col gap-1 rounded-sm border border-line bg-amber-soft px-3 py-2.5">
            {warnings.map((warning) => (
              <p key={warning} className="text-[11.5px] leading-[1.5] text-amber">
                {warning}
              </p>
            ))}
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <span className="o-eyebrow">Podgląd na przykładowych danych</span>
          <div className="rounded-sm border border-line bg-panel-2 px-3 py-2.5">
            <p className="mb-2 text-[12.5px] font-semibold text-text">
              {preview.subject || "(pusty temat)"}
            </p>
            <p className="whitespace-pre-wrap text-[12px] leading-[1.6] text-text-2">
              {preview.body}
            </p>
          </div>
        </div>
      </div>
    </Modal>
  );
}

export function WholesalerTemplatesSettings() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const templatesQuery = useWholesalerTemplates();
  const wholesalersQuery = useQuery({
    queryKey: ["wholesalers"],
    queryFn: () => window.ordly.wholesalers.list(),
  });
  const [draft, setDraft] = React.useState<WholesalerTemplateInput | null>(null);
  const [toDelete, setToDelete] = React.useState<WholesalerTemplate | null>(null);

  const templates = templatesQuery.data ?? [];
  const wholesalers = wholesalersQuery.data ?? [];
  const defaultTemplate = templates.find((t) => t.isDefault);

  function assignedNames(template: WholesalerTemplate): string[] {
    return wholesalers
      .filter((w) =>
        template.isDefault
          ? !w.templateId || !templates.some((t) => t.id === w.templateId)
          : w.templateId === template.id
      )
      .map((w) => w.name);
  }

  const setDefault = useMutation({
    mutationFn: (template: WholesalerTemplate) =>
      window.ordly.wholesalers.setDefaultTemplate(template.id),
    onSuccess: (_result, template) => {
      void queryClient.invalidateQueries({ queryKey: ["wholesaler-templates"] });
      toast.success("Zmieniono szablon domyślny", template.name);
    },
    onError: (error) => toast.error("Nie udało się zmienić domyślnego", errorMessage(error)),
  });

  const remove = useMutation({
    mutationFn: (template: WholesalerTemplate) =>
      window.ordly.wholesalers.deleteTemplate(template.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["wholesaler-templates"] });
      void queryClient.invalidateQueries({ queryKey: ["wholesalers"] });
      toast.success("Szablon usunięty", toDelete?.name);
      setToDelete(null);
    },
    onError: (error) => toast.error("Nie udało się usunąć szablonu", errorMessage(error)),
  });

  const deleteAssigned = toDelete ? assignedNames(toDelete) : [];

  return (
    <div className="flex flex-col gap-2">
      {templatesQuery.isError && (
        <p className="rounded-md border border-line bg-panel-2 px-[17px] py-[15px] text-[12px] leading-relaxed text-coral">
          Nie udało się wczytać szablonów. {errorMessage(templatesQuery.error)}
        </p>
      )}
      {templates.map((template) => {
        const assigned = assignedNames(template);
        return (
          <div
            key={template.id}
            className="flex items-center gap-4 rounded-md border border-line bg-panel-2 px-[17px] py-[13px]"
          >
            <div className="min-w-0 flex-1">
              <div className="mb-[3px] flex items-center gap-2">
                <h4 className="truncate text-[13px] font-semibold">{template.name}</h4>
                {template.isDefault && (
                  <span className="o-mono shrink-0 rounded-[20px] bg-teal-glow px-2 py-[2px] text-[10px] text-teal">
                    domyślny
                  </span>
                )}
              </div>
              <p className="line-clamp-1 text-[11.5px] leading-[1.45] text-text-3">
                {assigned.length === 0
                  ? template.isDefault
                    ? "Dla hurtowni bez przypisanego szablonu"
                    : "Nieprzypisany do żadnej hurtowni"
                  : `${template.isDefault ? "Używają" : "Przypisany"}: ${assigned.join(", ")}`}
              </p>
            </div>
            {!template.isDefault && (
              <MiniButton
                onClick={() => setDefault.mutate(template)}
                disabled={setDefault.isPending}
              >
                Ustaw jako domyślny
              </MiniButton>
            )}
            <MiniButton
              onClick={() =>
                setDraft({
                  id: template.id,
                  name: template.name,
                  subject: template.subject,
                  body: template.body,
                  inquirySubject: template.inquirySubject,
                  inquiryBody: template.inquiryBody,
                })
              }
            >
              Edytuj
            </MiniButton>
            <MiniButton
              onClick={() => setToDelete(template)}
              disabled={template.isDefault}
              title={
                template.isDefault
                  ? "Najpierw ustaw inny szablon jako domyślny"
                  : undefined
              }
              className="hover:!text-coral"
            >
              Usuń
            </MiniButton>
          </div>
        );
      })}
      {defaultTemplate && (
        <div>
          {/* Nowy szablon startuje z kopii domyslnego - zwykle zmienia sie
              jedno zdanie albo podpis, a nie pisze wszystko od zera. */}
          <MiniButton
            onClick={() =>
              setDraft({
                name: "",
                subject: defaultTemplate.subject,
                body: defaultTemplate.body,
                inquirySubject: defaultTemplate.inquirySubject,
                inquiryBody: defaultTemplate.inquiryBody,
              })
            }
          >
            + Dodaj szablon
          </MiniButton>
        </div>
      )}

      {draft && <TemplateEditor draft={draft} onClose={() => setDraft(null)} />}

      <ConfirmDialog
        open={toDelete !== null}
        title="Usunąć szablon?"
        message={
          deleteAssigned.length > 0
            ? `„${toDelete?.name ?? ""}” zniknie. ${deleteAssigned.join(", ")} ${
                deleteAssigned.length === 1 ? "wróci" : "wrócą"
              } do szablonu domyślnego.`
            : `„${toDelete?.name ?? ""}” zniknie z listy szablonów.`
        }
        confirmLabel="Usuń"
        pending={remove.isPending}
        onConfirm={() => toDelete && remove.mutate(toDelete)}
        onClose={() => setToDelete(null)}
      />
    </div>
  );
}
