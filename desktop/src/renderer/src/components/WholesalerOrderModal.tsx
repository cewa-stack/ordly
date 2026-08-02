import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { StockItem, Wholesaler } from "../types/api";
import { buildWholesalerBody, buildWholesalerSubject } from "../lib/wholesalerTemplate";
import { useToast } from "../lib/toast";

interface WholesalerOrderModalProps {
  item: StockItem;
  onClose: () => void;
}

const inputClass =
  "h-10 rounded-md border border-border bg-background px-3 text-body text-text focus:border-primary focus:outline-none";

function useWholesalers() {
  return useQuery({
    queryKey: ["wholesalers"],
    queryFn: () => window.ordly.wholesalers.list(),
  });
}

export function WholesalerOrderModal({ item, onClose }: WholesalerOrderModalProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { data: wholesalers } = useWholesalers();
  const [selectedId, setSelectedId] = React.useState<string>("__new__");
  const [newName, setNewName] = React.useState("");
  const [newEmail, setNewEmail] = React.useState("");
  const [quantity, setQuantity] = React.useState(Math.max(item.min_stock - item.stock, 1));
  const [subject, setSubject] = React.useState(() =>
    buildWholesalerSubject([{ sku: item.sku, name: item.name, quantity: 1 }])
  );
  const [body, setBody] = React.useState("");
  const [bodyTouched, setBodyTouched] = React.useState(false);

  const wholesalerList = React.useMemo(() => wholesalers ?? [], [wholesalers]);
  const selected = wholesalerList.find((w) => w.id === selectedId);

  React.useEffect(() => {
    if (bodyTouched) return;
    const wholesalerForTemplate: Wholesaler = selected ?? {
      id: "",
      name: newName || "Hurtownia",
      email: newEmail,
      linkedSkus: [],
    };
    setBody(buildWholesalerBody(wholesalerForTemplate, [{ sku: item.sku, name: item.name, quantity }]));
  }, [selected, newName, newEmail, quantity, bodyTouched, item.sku, item.name]);

  React.useEffect(() => {
    setSubject(buildWholesalerSubject([{ sku: item.sku, name: item.name, quantity }]));
  }, [item.sku, item.name, quantity]);

  const sendMutation = useMutation({
    mutationFn: async () => {
      let wholesaler = selected;
      if (!wholesaler) {
        if (!newName.trim() || !newEmail.trim()) {
          throw new Error("Podaj nazwę i e-mail hurtowni.");
        }
        wholesaler = await window.ordly.wholesalers.save({
          name: newName.trim(),
          email: newEmail.trim(),
          linkedSkus: [item.sku],
        });
        void queryClient.invalidateQueries({ queryKey: ["wholesalers"] });
      }
      const result = await window.ordly.wholesalers.sendOrder({
        wholesalerId: wholesaler.id,
        wholesalerName: wholesaler.name,
        to: wholesaler.email,
        subject,
        body,
        itemsSummary: `${item.name} (${item.sku}) x${quantity}`,
      });
      if (!result.ok) throw new Error(result.message);
      return wholesaler;
    },
    onSuccess: (wholesaler) => {
      void queryClient.invalidateQueries({ queryKey: ["wholesaler-history"] });
      toast.success(`Zamówienie wysłane do ${wholesaler.name}`);
      onClose();
    },
  });

  const canSend = Boolean(
    (selected || (newName.trim() && newEmail.trim())) && subject.trim() && body.trim()
  );

  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="flex max-h-[85vh] w-full max-w-lg flex-col overflow-y-auto rounded-2xl border border-border bg-surface p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-headline">Zamów u hurtowni</h2>
        <p className="mt-1 text-footnote text-text-secondary">
          {item.name} · SKU {item.sku}
        </p>

        <div className="mt-4 flex flex-col gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-secondary">Hurtownia</span>
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className={`${inputClass} ordly-select`}
            >
              <option value="__new__">+ Nowa hurtownia</option>
              {wholesalerList.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </label>

          {selectedId === "__new__" && (
            <div className="flex gap-2">
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Nazwa hurtowni"
                className={`${inputClass} flex-1`}
              />
              <input
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                placeholder="email@hurtownia.pl"
                className={`${inputClass} flex-1`}
              />
            </div>
          )}

          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-secondary">Ilość</span>
            <input
              type="number"
              min={1}
              value={quantity}
              onChange={(e) => setQuantity(Math.max(1, Number(e.target.value)))}
              className={inputClass}
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-secondary">Temat</span>
            <input value={subject} onChange={(e) => setSubject(e.target.value)} className={inputClass} />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-secondary">Treść</span>
            <textarea
              value={body}
              onChange={(e) => {
                setBody(e.target.value);
                setBodyTouched(true);
              }}
              rows={8}
              className="resize-none rounded-md border border-border bg-background px-3 py-2 text-body text-text focus:border-primary focus:outline-none"
            />
          </label>
        </div>

        {sendMutation.isError && (
          <p className="mt-3 text-caption text-danger">
            {sendMutation.error instanceof Error ? sendMutation.error.message : "Nie udało się wysłać maila."}
          </p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-callout-semibold text-text-secondary hover:bg-surface-raised">
            Anuluj
          </button>
          <button
            onClick={() => sendMutation.mutate()}
            disabled={!canSend || sendMutation.isPending}
            className="rounded-lg bg-gradient-to-br from-primary to-accent px-4 py-2 text-callout-semibold text-on-primary shadow-[0_8px_18px_-8px_rgba(86,224,208,0.5)] disabled:opacity-45"
          >
            {sendMutation.isPending ? "Wysyłanie…" : "Wyślij"}
          </button>
        </div>
      </div>
    </div>
  );
}
