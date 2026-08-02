import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PlusIcon } from "../icons";
import { EmptyState } from "../components/EmptyState";
import { useToast } from "../lib/toast";
import type { Wholesaler } from "../types/api";

const dateFormatter = new Intl.DateTimeFormat("pl-PL", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const inputClass =
  "h-10 rounded-md border border-border bg-background px-3 text-body text-text focus:border-primary focus:outline-none";

function useWholesalers() {
  return useQuery({ queryKey: ["wholesalers"], queryFn: () => window.ordly.wholesalers.list() });
}

function useWholesalerHistory() {
  return useQuery({
    queryKey: ["wholesaler-history"],
    queryFn: () => window.ordly.wholesalers.history(),
  });
}

interface WholesalerFormModalProps {
  wholesaler: Wholesaler | null;
  onClose: () => void;
}

function WholesalerFormModal({ wholesaler, onClose }: WholesalerFormModalProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [name, setName] = React.useState(wholesaler?.name ?? "");
  const [email, setEmail] = React.useState(wholesaler?.email ?? "");
  const [contactPerson, setContactPerson] = React.useState(wholesaler?.contactPerson ?? "");
  const [skus, setSkus] = React.useState(wholesaler?.linkedSkus.join(", ") ?? "");

  const saveMutation = useMutation({
    mutationFn: () =>
      window.ordly.wholesalers.save({
        id: wholesaler?.id,
        name: name.trim(),
        email: email.trim(),
        contactPerson: contactPerson.trim() || undefined,
        linkedSkus: skus
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      }),
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ["wholesalers"] });
      toast.success(wholesaler ? `${saved.name} zaktualizowana` : `${saved.name} dodana`);
      onClose();
    },
  });

  const canSave = name.trim().length > 0 && email.trim().includes("@");

  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl border border-border bg-surface p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-headline">{wholesaler ? "Edytuj hurtownię" : "Nowa hurtownia"}</h2>
        <div className="mt-4 flex flex-col gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-secondary">Nazwa</span>
            <input value={name} onChange={(e) => setName(e.target.value)} className={inputClass} />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-secondary">E-mail</span>
            <input value={email} onChange={(e) => setEmail(e.target.value)} className={inputClass} />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-secondary">Osoba kontaktowa (opcjonalnie)</span>
            <input
              value={contactPerson}
              onChange={(e) => setContactPerson(e.target.value)}
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-secondary">Powiązane SKU (po przecinku, opcjonalnie)</span>
            <input value={skus} onChange={(e) => setSkus(e.target.value)} className={inputClass} />
          </label>
        </div>

        {saveMutation.isError && (
          <p className="mt-3 text-caption text-danger">Nie udało się zapisać hurtowni.</p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-callout-semibold text-text-secondary hover:bg-surface-raised">
            Anuluj
          </button>
          <button
            onClick={() => saveMutation.mutate()}
            disabled={!canSave || saveMutation.isPending}
            className="rounded-lg bg-gradient-to-br from-primary to-accent px-4 py-2 text-callout-semibold text-on-primary shadow-[0_8px_18px_-8px_rgba(86,224,208,0.5)] disabled:opacity-45"
          >
            {saveMutation.isPending ? "Zapisywanie…" : "Zapisz"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function HurtowniaScreen() {
  const { data: wholesalers, isLoading } = useWholesalers();
  const { data: history, isLoading: isHistoryLoading } = useWholesalerHistory();
  const queryClient = useQueryClient();
  const [editing, setEditing] = React.useState<Wholesaler | null | "new">(null);

  const deleteMutation = useMutation({
    mutationFn: (id: string) => window.ordly.wholesalers.delete(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["wholesalers"] }),
  });

  return (
    <div>
      <div className="mb-5 flex items-center justify-between gap-4">
        <h1 className="text-title1">Hurtownia</h1>
        <button
          onClick={() => setEditing("new")}
          className="flex h-9 items-center gap-2 rounded-[10px] bg-gradient-to-br from-primary to-accent px-3.5 text-[12.5px] font-bold text-on-primary"
        >
          <PlusIcon size={14} className="text-on-primary" />
          Dodaj hurtownię
        </button>
      </div>

      <h2 className="mb-2 text-headline text-text-secondary">Hurtownie</h2>
      {isLoading && <p className="text-footnote text-text-secondary">Wczytywanie…</p>}
      {!isLoading && wholesalers && wholesalers.length === 0 && (
        <EmptyState
          pose="thinking"
          title="Brak zapisanych hurtowni"
          description="Dodaj pierwszą hurtownię albo utwórz ją od razu przy zamawianiu z ekranu Magazyn."
        />
      )}
      {wholesalers && wholesalers.length > 0 && (
        <div className="flex flex-col gap-2">
          {wholesalers.map((w) => (
            <div
              key={w.id}
              className="flex items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-callout-semibold">{w.name}</p>
                <p className="truncate text-[12px] text-text-secondary">
                  {w.email}
                  {w.contactPerson ? ` · ${w.contactPerson}` : ""}
                  {w.linkedSkus.length > 0 ? ` · ${w.linkedSkus.length} SKU` : ""}
                </p>
              </div>
              <button
                onClick={() => setEditing(w)}
                className="shrink-0 rounded-lg px-2.5 py-1 text-[11.5px] font-semibold text-primary hover:bg-primary-tint"
              >
                Edytuj
              </button>
              <button
                onClick={() => deleteMutation.mutate(w.id)}
                className="shrink-0 rounded-lg px-2.5 py-1 text-[11.5px] font-semibold text-danger hover:bg-danger-tint"
              >
                Usuń
              </button>
            </div>
          ))}
        </div>
      )}

      <h2 className="mb-2 mt-8 text-headline text-text-secondary">Historia zamówień</h2>
      {isHistoryLoading && <p className="text-footnote text-text-secondary">Wczytywanie…</p>}
      {!isHistoryLoading && history && history.length === 0 && (
        <p className="text-footnote text-text-secondary">Nie wysłano jeszcze żadnego zamówienia.</p>
      )}
      {history && history.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                {["Data", "Hurtownia", "Temat", "Produkty"].map((h) => (
                  <th
                    key={h}
                    className="border-b border-border px-4 py-2.5 text-left font-mono text-[10.5px] uppercase tracking-wide text-text-dim"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {history.map((record, rowIndex) => {
                const cellBorder = rowIndex === history.length - 1 ? "" : "border-b border-border";
                return (
                  <tr key={record.id}>
                    <td className={`px-4 py-3 text-[12px] tabular-nums text-text-secondary ${cellBorder}`}>
                      {dateFormatter.format(new Date(record.sentAt))}
                    </td>
                    <td className={`px-4 py-3 text-[13px] ${cellBorder}`}>{record.wholesalerName}</td>
                    <td className={`px-4 py-3 text-[12.5px] text-text-secondary ${cellBorder}`}>
                      {record.subject}
                    </td>
                    <td className={`px-4 py-3 text-[12.5px] text-text-secondary ${cellBorder}`}>
                      {record.itemsSummary}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <WholesalerFormModal
          wholesaler={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}
