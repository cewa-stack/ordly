/**
 * Hurtownie - siatka 3 kolumn (sekcja 4.4). Karta: znak literowy, nazwa,
 * liczba zapisanych pozycji, przycisk "Napisz zamówienie".
 *
 * Kazda hurtownia ma WLASNA liste pozycji, wpisywana recznie tutaj. To
 * nie ma zwiazku z Magazynem: kupuje sie surowce i opakowania, a sprzedaje
 * gotowe oferty, wiec proba wiazania jednego z drugim po SKU tylko myli.
 *
 * Koncepcja pokazuje na karcie "czas dostawy" - ORDLY tego nie ma
 * w danych, wiec zamiast wymyslonej liczby dni karta pokazuje realny fakt:
 * ile pozycji ma zapisana lista.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MailIcon, PencilIcon, PlusIcon, TrashIcon } from "../icons";
import {
  Button,
  EmptyState,
  MiniButton,
  SectionLabel,
  SkeletonRows,
} from "../components/ui";
import { ConfirmDialog, Modal } from "../components/Modal";
import { WholesalerOrderModal } from "../components/WholesalerOrderModal";
import { useToast } from "../lib/toast";
import { formatDateTime, formatPlural } from "../lib/format";
import type { Wholesaler, WholesalerItem } from "../types/api";

const inputClass =
  "w-full rounded-sm border border-line bg-base px-3 py-2.5 text-[12.5px] text-text outline-none focus:border-teal";

function WholesalerFormModal({
  wholesaler,
  onClose,
}: {
  wholesaler: Wholesaler | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [name, setName] = React.useState(wholesaler?.name ?? "");
  const [email, setEmail] = React.useState(wholesaler?.email ?? "");
  const [contactPerson, setContactPerson] = React.useState(wholesaler?.contactPerson ?? "");
  // Pusty wiersz na koncu, zeby dopisanie pozycji nie wymagalo najpierw
  // klikniecia "Dodaj pozycję" - pusta nazwa i tak wypada przy zapisie.
  const [items, setItems] = React.useState<WholesalerItem[]>([
    ...(wholesaler?.items ?? []),
    { name: "", quantity: 1 },
  ]);

  function patchItem(index: number, patch: Partial<WholesalerItem>) {
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      window.ordly.wholesalers.save({
        id: wholesaler?.id,
        name: name.trim(),
        email: email.trim(),
        contactPerson: contactPerson.trim() || undefined,
        items: items
          .filter((item) => item.name.trim().length > 0)
          .map((item) => ({ name: item.name.trim(), quantity: Math.max(1, item.quantity) })),
      }),
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ["wholesalers"] });
      toast.success(
        wholesaler ? "Zapisano zmiany" : "Dodano hurtownię",
        `${saved.name} · ${saved.email}`
      );
      onClose();
    },
    onError: () => {
      toast.error("Nie udało się zapisać", "Sprawdź dane i spróbuj ponownie.");
    },
  });

  const canSave = name.trim().length > 0 && email.trim().includes("@");

  return (
    <Modal
      open
      onClose={onClose}
      title={wholesaler ? "Edytuj hurtownię" : "Nowa hurtownia"}
      width={480}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={saveMutation.isPending}>
            Anuluj
          </Button>
          <Button onClick={() => saveMutation.mutate()} disabled={!canSave || saveMutation.isPending}>
            {saveMutation.isPending ? "Zapisuję…" : "Zapisz"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <label className="flex flex-col gap-1.5">
          <span className="o-eyebrow">Nazwa</span>
          <input value={name} onChange={(e) => setName(e.target.value)} className={inputClass} />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="o-eyebrow">E-mail</span>
          <input value={email} onChange={(e) => setEmail(e.target.value)} className={inputClass} />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="o-eyebrow">Osoba kontaktowa</span>
          <input
            value={contactPerson}
            onChange={(e) => setContactPerson(e.target.value)}
            placeholder="opcjonalnie - trafia do powitania w mailu"
            className={inputClass}
          />
        </label>
        <div className="flex flex-col gap-1.5">
          <span className="o-eyebrow">Co się tu zamawia</span>
          {items.map((item, index) => (
            <div key={index} className="flex gap-2">
              <input
                value={item.name}
                onChange={(e) => patchItem(index, { name: e.target.value })}
                placeholder="Nazwa pozycji"
                className={inputClass}
              />
              <input
                type="number"
                min={1}
                value={item.quantity}
                onChange={(e) =>
                  patchItem(index, { quantity: Math.max(1, Number(e.target.value) || 1) })
                }
                aria-label="Ilość"
                className={`${inputClass} o-mono !w-[76px] shrink-0 text-center`}
              />
              <MiniButton
                className="!px-2 hover:!text-coral"
                onClick={() => setItems((prev) => prev.filter((_, i) => i !== index))}
                aria-label="Usuń pozycję"
              >
                <TrashIcon size={13} />
              </MiniButton>
            </div>
          ))}
          <MiniButton
            className="self-start"
            icon={<PlusIcon size={13} />}
            onClick={() => setItems((prev) => [...prev, { name: "", quantity: 1 }])}
          >
            Dodaj pozycję
          </MiniButton>
          <span className="text-[11px] text-text-3">
            Lista tej hurtowni - co u niej kupujesz i ile zwykle bierzesz. Przy pisaniu
            maila wszystko jest zaznaczone, odznaczasz to, czego akurat nie trzeba.
          </span>
        </div>
      </div>
    </Modal>
  );
}

export function HurtowniaScreen() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = React.useState<Wholesaler | null | "new">(null);
  const [ordering, setOrdering] = React.useState<Wholesaler | null>(null);
  const [deleting, setDeleting] = React.useState<Wholesaler | null>(null);

  const wholesalersQuery = useQuery({
    queryKey: ["wholesalers"],
    queryFn: () => window.ordly.wholesalers.list(),
  });

  const historyQuery = useQuery({
    queryKey: ["wholesaler-history"],
    queryFn: () => window.ordly.wholesalers.history(),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => window.ordly.wholesalers.delete(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["wholesalers"] });
      setDeleting(null);
      toast.success("Usunięto hurtownię", "Historia wysłanych zamówień zostaje.");
    },
  });

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto p-[22px]">
      <div className="flex items-center gap-3">
        <SectionLabel>Dostawcy</SectionLabel>
        <MiniButton
          className="ml-auto"
          icon={<PlusIcon size={13} />}
          onClick={() => setEditing("new")}
        >
          Dodaj hurtownię
        </MiniButton>
      </div>

      {wholesalersQuery.isLoading && <SkeletonRows rows={2} />}
      {!wholesalersQuery.isLoading && (wholesalersQuery.data ?? []).length === 0 && (
        <EmptyState
          title="Brak zapisanych hurtowni"
          description="Dodaj pierwszą hurtownię i wpisz, co się w niej zamawia - Ordi złoży z tego gotowego maila."
        />
      )}

      <div className="grid grid-cols-3 gap-3 max-[1100px]:grid-cols-2 max-[940px]:grid-cols-1">
        {(wholesalersQuery.data ?? []).map((wholesaler) => (
          <div
            key={wholesaler.id}
            className="flex flex-col gap-[11px] rounded-md border border-line bg-panel-2 p-[17px] transition-[border-color,transform] duration-[180ms] ease-ordly hover:-translate-y-0.5 hover:border-line-2"
          >
            <div className="flex items-start gap-2">
              <span className="o-display flex h-[34px] w-[34px] items-center justify-center rounded-[10px] bg-panel-3 text-[13px] font-semibold text-teal">
                {wholesaler.name.slice(0, 1).toUpperCase()}
              </span>
              <div className="ml-auto flex gap-1">
                <MiniButton
                  className="!px-2"
                  onClick={() => setEditing(wholesaler)}
                  aria-label="Edytuj"
                >
                  <PencilIcon size={13} />
                </MiniButton>
                <MiniButton
                  className="!px-2 hover:!text-coral"
                  onClick={() => setDeleting(wholesaler)}
                  aria-label="Usuń"
                >
                  <TrashIcon size={13} />
                </MiniButton>
              </div>
            </div>
            <h4 className="text-[13.5px] font-semibold truncate">{wholesaler.name}</h4>
            <p className="o-mono truncate text-[10.5px] text-text-3">{wholesaler.email}</p>
            <p className="o-mono text-[10.5px] text-text-3">
              {wholesaler.items.length === 0
                ? "brak zapisanych pozycji"
                : formatPlural(wholesaler.items.length, ["pozycja", "pozycje", "pozycji"])}
            </p>
            {/* Przycisk jest zawsze aktywny - pusta lista pozycji nie jest
                powodem, zeby nie dalo sie napisac do hurtowni (zapytanie
                o cennik, termin, nowy produkt). */}
            <Button
              className="mt-1 !px-3 !py-2 !text-[11.5px]"
              onClick={() => setOrdering(wholesaler)}
              icon={<MailIcon size={13} />}
            >
              Napisz zamówienie
            </Button>
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-col gap-2">
        <SectionLabel>Wysłane zamówienia</SectionLabel>
        {historyQuery.isLoading && <SkeletonRows rows={2} />}
        {!historyQuery.isLoading && (historyQuery.data ?? []).length === 0 && (
          <p className="text-[12.5px] text-text-3">
            Nie wysłano jeszcze żadnego zamówienia do hurtowni.
          </p>
        )}
        {(historyQuery.data ?? []).map((record) => (
          <div
            key={record.id}
            className="flex items-center gap-3 rounded-md border border-line bg-panel-2 px-4 py-3 text-[12.5px]"
          >
            <span className="o-mono w-[110px] shrink-0 text-[10.5px] text-text-3">
              {formatDateTime(record.sentAt)}
            </span>
            <span className="w-[130px] shrink-0 truncate font-medium">
              {record.wholesalerName}
            </span>
            <span className="min-w-0 flex-1 truncate text-text-2">{record.itemsSummary}</span>
          </div>
        ))}
      </div>

      {editing && (
        <WholesalerFormModal
          wholesaler={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}

      <WholesalerOrderModal
        open={ordering !== null}
        onClose={() => setOrdering(null)}
        preselected={ordering}
      />

      <ConfirmDialog
        open={deleting !== null}
        title={`Usunąć ${deleting?.name ?? ""}?`}
        message="Hurtownia zniknie z listy i z podpowiedzi przy zamawianiu. Historia wysłanych maili zostaje nietknięta."
        confirmLabel="Usuń hurtownię"
        pending={deleteMutation.isPending}
        onConfirm={() => deleting && deleteMutation.mutate(deleting.id)}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}
