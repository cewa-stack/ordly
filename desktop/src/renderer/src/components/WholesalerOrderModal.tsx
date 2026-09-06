/**
 * Kompozytor maila do hurtowni (sekcja 9.1 pkt 9).
 *
 * Modal dostaje CALY asortyment danej hurtowni (produkty powiazane z nia
 * przez SKU), a nie tylko to, czego brakuje. Pozycje ponizej progu sa
 * zaznaczone z gory, reszte zaznacza sie recznie.
 *
 * Wczesniej modal przyjmowal wylacznie produkty ponizej progu i blokowal
 * wysylke przy pustej liscie - przez co przy pelnym magazynie nie dalo sie
 * w ogole napisac do hurtowni (np. zapytac o cennik). Mail bez pozycji jest
 * teraz normalna sciezka: licza sie adresat, temat i tresc.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Modal } from "./Modal";
import { Button, Stepper } from "./ui";
import { buildWholesalerBody, buildWholesalerSubject } from "../lib/wholesalerTemplate";
import { useToast } from "../lib/toast";
import type { StockItem, Wholesaler } from "../types/api";

interface WholesalerOrderModalProps {
  open: boolean;
  onClose: () => void;
  /** Produkty, ktore mozna zamowic w tej hurtowni (cale jej powiazane SKU). */
  items: StockItem[];
  /** SKU zaznaczone od razu po otwarciu - zwykle te ponizej progu. */
  initialSelection?: string[];
  /** Hurtownia wybrana z gory (klikniecie "Napisz zamówienie" na karcie). */
  preselected?: Wholesaler | null;
}

const inputClass =
  "w-full rounded-sm border border-line bg-ink-raised px-3 py-2.5 text-[12.5px] text-white outline-none focus:border-teal-bright";

/** Ilosc do uzupelnienia: brakuje do progu, minimum 1 sztuka. */
function suggestedQuantity(item: StockItem): number {
  return Math.max(item.min_stock - item.stock, 1);
}

export function WholesalerOrderModal({
  open,
  onClose,
  items,
  initialSelection,
  preselected = null,
}: WholesalerOrderModalProps) {
  const queryClient = useQueryClient();
  const toast = useToast();

  const { data: wholesalers } = useQuery({
    queryKey: ["wholesalers"],
    queryFn: () => window.ordly.wholesalers.list(),
    enabled: open,
  });

  const [selectedId, setSelectedId] = React.useState(preselected?.id ?? "__new__");
  const [newName, setNewName] = React.useState("");
  const [newEmail, setNewEmail] = React.useState("");
  const [checked, setChecked] = React.useState<Record<string, boolean>>({});
  const [quantities, setQuantities] = React.useState<Record<string, number>>({});
  const [subject, setSubject] = React.useState("");
  const [body, setBody] = React.useState("");
  const [bodyTouched, setBodyTouched] = React.useState(false);

  // Klucze zawartosci, nie same tablice: identycznosc `items` zmienia sie
  // przy kazdym renderze rodzica, wiec tablica w zaleznosciach efektu
  // kasowalaby zaznaczenia i ilosci w trakcie pisania maila.
  const itemsKey = items.map((item) => item.sku).join(",");
  const selectionKey = (initialSelection ?? []).join(",");

  React.useEffect(() => {
    if (!open) return;
    setSelectedId(preselected?.id ?? "__new__");
    setBodyTouched(false);
    const preset = new Set(initialSelection ?? []);
    setChecked(Object.fromEntries(items.map((item) => [item.sku, preset.has(item.sku)])));
    setQuantities(Object.fromEntries(items.map((item) => [item.sku, suggestedQuantity(item)])));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, preselected, itemsKey, selectionKey]);

  const selected = (wholesalers ?? []).find((w) => w.id === selectedId) ?? null;

  const orderItems = React.useMemo(
    () =>
      items
        .filter((item) => checked[item.sku])
        .map((item) => ({
          sku: item.sku,
          name: item.name,
          quantity: quantities[item.sku] ?? suggestedQuantity(item),
        })),
    [items, checked, quantities]
  );

  React.useEffect(() => {
    if (!open) return;
    if (bodyTouched) return;
    setSubject(buildWholesalerSubject(orderItems));
    const target: Wholesaler = selected ?? {
      id: "",
      name: newName || "Hurtownia",
      email: newEmail,
      linkedSkus: [],
    };
    setBody(buildWholesalerBody(target, orderItems));
  }, [open, orderItems, selected, newName, newEmail, bodyTouched]);

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
          linkedSkus: orderItems.map((item) => item.sku),
        });
        void queryClient.invalidateQueries({ queryKey: ["wholesalers"] });
      }
      const result = await window.ordly.wholesalers.sendOrder({
        wholesalerId: wholesaler.id,
        wholesalerName: wholesaler.name,
        to: wholesaler.email,
        subject,
        body,
        itemsSummary:
          orderItems.length === 0
            ? "wiadomość bez pozycji"
            : orderItems
                .map((item) => `${item.name} (${item.sku}) x${item.quantity}`)
                .join(", "),
      });
      if (!result.ok) throw new Error(result.message);
      return wholesaler;
    },
    onSuccess: (wholesaler) => {
      void queryClient.invalidateQueries({ queryKey: ["wholesaler-history"] });
      toast.success(
        "Mail wysłany",
        orderItems.length === 0
          ? `${wholesaler.name} · wiadomość bez pozycji`
          : `${wholesaler.name} · ${orderItems.length} ${
              orderItems.length === 1 ? "pozycja" : "pozycji"
            }`
      );
      onClose();
    },
    onError: (error) => {
      toast.error(
        "Mail nie wyszedł",
        error instanceof Error
          ? error.message
          : "Sprawdź konfigurację SMTP w .env na Pi i spróbuj ponownie."
      );
    },
  });

  // Pozycje sa opcjonalne - mail do hurtowni bywa zwyklym pytaniem o cennik
  // albo termin. Twardo wymagany jest adresat, temat i niepusta tresc.
  const canSend = Boolean(
    (selected || (newName.trim() && newEmail.trim())) && subject.trim() && body.trim()
  );

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Napisz zamówienie"
      subtitle={
        items.length === 0
          ? "Brak powiązanych produktów - napisz zwykłą wiadomość"
          : `${orderItems.length} z ${items.length} ${
              items.length === 1 ? "produktu" : "produktów"
            } zaznaczonych`
      }
      width={600}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={sendMutation.isPending}>
            Anuluj
          </Button>
          <Button
            onClick={() => sendMutation.mutate()}
            disabled={!canSend || sendMutation.isPending}
          >
            {sendMutation.isPending ? "Wysyłam…" : "Wyślij maila"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <label className="flex flex-col gap-1.5">
          <span className="o-eyebrow">Hurtownia</span>
          <select
            value={selectedId}
            onChange={(event) => setSelectedId(event.target.value)}
            className={inputClass}
          >
            <option value="__new__">+ Nowa hurtownia</option>
            {(wholesalers ?? []).map((wholesaler) => (
              <option key={wholesaler.id} value={wholesaler.id}>
                {wholesaler.name}
              </option>
            ))}
          </select>
        </label>

        {selectedId === "__new__" && (
          <div className="flex gap-2">
            <input
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              placeholder="Nazwa hurtowni"
              className={inputClass}
            />
            <input
              value={newEmail}
              onChange={(event) => setNewEmail(event.target.value)}
              placeholder="email@hurtownia.pl"
              className={inputClass}
            />
          </div>
        )}

        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <span className="o-eyebrow">Pozycje</span>
            <span className="text-[10.5px] text-slate-dim">opcjonalne</span>
          </div>
          {items.length === 0 && (
            <p className="text-[12px] leading-[1.6] text-slate-dim">
              Ta hurtownia nie ma powiązanych produktów w magazynie. Możesz i tak wysłać
              wiadomość - wpisz treść niżej.
            </p>
          )}
          {items.map((item) => {
            const isChecked = Boolean(checked[item.sku]);
            return (
              <div
                key={item.sku}
                className={`flex items-center gap-3 rounded-sm border px-3 py-2 transition-colors ${
                  isChecked ? "border-line-strong bg-panel-3" : "border-line bg-panel-2"
                }`}
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={(event) =>
                    setChecked((prev) => ({ ...prev, [item.sku]: event.target.checked }))
                  }
                  aria-label={`Dodaj ${item.name} do zamówienia`}
                  className="h-[15px] w-[15px] shrink-0 accent-[var(--teal-bright)]"
                />
                <span className="min-w-0 flex-1 truncate text-[12.5px] text-white">
                  {item.name}
                </span>
                {item.is_low_stock && (
                  <span className="o-mono shrink-0 text-[10px] text-coral">poniżej progu</span>
                )}
                <span className="o-mono shrink-0 text-[11px] text-slate-dim">
                  {item.stock} szt.
                </span>
                <Stepper
                  value={quantities[item.sku] ?? suggestedQuantity(item)}
                  onDecrease={() =>
                    setQuantities((prev) => ({
                      ...prev,
                      [item.sku]: Math.max(1, (prev[item.sku] ?? suggestedQuantity(item)) - 1),
                    }))
                  }
                  onIncrease={() =>
                    setQuantities((prev) => ({
                      ...prev,
                      [item.sku]: (prev[item.sku] ?? suggestedQuantity(item)) + 1,
                    }))
                  }
                />
              </div>
            );
          })}
        </div>

        <label className="flex flex-col gap-1.5">
          <span className="o-eyebrow">Temat</span>
          <input
            value={subject}
            onChange={(event) => {
              setSubject(event.target.value);
              setBodyTouched(true);
            }}
            className={inputClass}
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="o-eyebrow">Treść</span>
          <textarea
            value={body}
            onChange={(event) => {
              setBody(event.target.value);
              setBodyTouched(true);
            }}
            rows={9}
            className={`${inputClass} resize-none leading-[1.6]`}
          />
        </label>
      </div>
    </Modal>
  );
}
