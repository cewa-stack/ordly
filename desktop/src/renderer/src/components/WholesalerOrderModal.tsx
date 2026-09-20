/**
 * Kompozytor maila do hurtowni (sekcja 9.1 pkt 9).
 *
 * Pozycje sa wlasnoscia hurtowni, nie magazynu - to lista tego, co sie
 * u niej kupuje (surowiec, opakowanie), a to rzadko jest tym samym, co
 * stoi w ofertach. Dlatego zmiana hurtowni w liscie rozwijanej podmienia
 * cala liste pozycji.
 *
 * Mail bez pozycji jest normalna sciezka: do hurtowni pisze sie tez po to,
 * zeby zapytac o cennik albo termin. Wymagany jest adresat, temat i tresc.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Modal } from "./Modal";
import { Button, Stepper } from "./ui";
import { buildWholesalerBody, buildWholesalerSubject } from "../lib/wholesalerTemplate";
import { formatPlural } from "../lib/format";
import { useToast } from "../lib/toast";
import type { Wholesaler } from "../types/api";

interface WholesalerOrderModalProps {
  open: boolean;
  onClose: () => void;
  /** Hurtownia wybrana z gory (klikniecie "Napisz zamówienie" na karcie). */
  preselected?: Wholesaler | null;
}

const inputClass =
  "w-full rounded-sm border border-line bg-base px-3 py-2.5 text-[12.5px] text-text outline-none focus:border-teal";

export function WholesalerOrderModal({
  open,
  onClose,
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

  const selected = (wholesalers ?? []).find((w) => w.id === selectedId) ?? null;
  const items = React.useMemo(() => selected?.items ?? [], [selected]);

  React.useEffect(() => {
    if (!open) return;
    setSelectedId(preselected?.id ?? "__new__");
    setBodyTouched(false);
  }, [open, preselected]);

  // Klucz zawartosci, nie sama tablica: `items` to nowy obiekt przy kazdym
  // odswiezeniu zapytania w tle, wiec tablica w zaleznosciach efektu
  // kasowalaby zaznaczenia i ilosci w trakcie pisania maila.
  const itemsKey = items.map((item) => `${item.name}:${item.quantity}`).join("|");

  React.useEffect(() => {
    if (!open) return;
    // Lista pozycji hurtowni JEST jej lista zakupowa - domyslnie zaznaczone
    // jest wszystko, odznacza sie to, czego akurat nie trzeba.
    setChecked(Object.fromEntries(items.map((item) => [item.name, true])));
    setQuantities(Object.fromEntries(items.map((item) => [item.name, item.quantity])));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, itemsKey]);

  const orderItems = React.useMemo(
    () =>
      items
        .filter((item) => checked[item.name])
        .map((item) => ({
          name: item.name,
          quantity: quantities[item.name] ?? item.quantity,
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
      items: [],
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
          items: orderItems,
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
            : orderItems.map((item) => `${item.name} x${item.quantity}`).join(", "),
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
          : `${wholesaler.name} · ${formatPlural(orderItems.length, [
              "pozycja",
              "pozycje",
              "pozycji",
            ])}`
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
          ? "Hurtownia bez zapisanych pozycji - napisz zwykłą wiadomość"
          : `Zaznaczone ${orderItems.length} z ${items.length} pozycji`
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
            <span className="text-[10.5px] text-text-3">opcjonalne</span>
          </div>
          {items.length === 0 && (
            <p className="text-[12px] leading-[1.6] text-text-3">
              Ta hurtownia nie ma jeszcze zapisanych pozycji. Dopisz je w edycji hurtowni
              albo wyślij samą wiadomość - treść wpiszesz niżej.
            </p>
          )}
          {items.map((item) => {
            const isChecked = Boolean(checked[item.name]);
            return (
              <div
                key={item.name}
                className={`flex items-center gap-3 rounded-sm border px-3 py-2 transition-colors ${
                  isChecked ? "border-line-2 bg-panel-3" : "border-line bg-panel-2"
                }`}
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={(event) =>
                    setChecked((prev) => ({ ...prev, [item.name]: event.target.checked }))
                  }
                  aria-label={`Dodaj ${item.name} do zamówienia`}
                  className="h-[15px] w-[15px] shrink-0 accent-[var(--teal-bright)]"
                />
                <span className="min-w-0 flex-1 truncate text-[12.5px] text-text">
                  {item.name}
                </span>
                <Stepper
                  value={quantities[item.name] ?? item.quantity}
                  onDecrease={() =>
                    setQuantities((prev) => ({
                      ...prev,
                      [item.name]: Math.max(1, (prev[item.name] ?? item.quantity) - 1),
                    }))
                  }
                  onIncrease={() =>
                    setQuantities((prev) => ({
                      ...prev,
                      [item.name]: (prev[item.name] ?? item.quantity) + 1,
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
