/**
 * Ordlak - generator ofert Allegro.
 *
 * Uklad "formularz + wynik" (`minmax(0,1fr) minmax(0,1fr)`), historia pod
 * spodem jako trzecia zakladka wyniku. Kazdy przycisk na tym ekranie ma
 * pokrycie w backendzie - kopiowanie idzie do schowka systemowego,
 * "Zapisz poprawki" wola `POST /api/v1/ordlak/{id}/finalize`, a suwak
 * marzy przelicza cene lokalnie tym samym wzorem co backend.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Chip,
  ErrorState,
  MiniButton,
  SectionLabel,
  SkeletonRows,
} from "../components/ui";
import { OrdlakMascot, type OrdlakPose } from "../components/OrdlakMascot";
import { AlertIcon, CheckIcon, ClipIcon, RefreshIcon, TrashIcon } from "../icons";
import { useToast } from "../lib/toast";
import { formatCurrency, formatDateTime } from "../lib/format";
import { calculatePricePreview } from "../lib/ordlakPrice";
import { sanitizeOfferHtml } from "../lib/sanitizeHtml";
import type {
  OrdlakCondition,
  OrdlakGeneration,
  OrdlakHistoryItem,
  OrdlakPhotoPayload,
  OrdlakPriceBreakdown,
} from "../types/api";

const CONDITION_LABEL: Record<OrdlakCondition, string> = {
  new: "Nowy",
  very_good: "Bardzo dobry",
  good: "Dobry",
  damaged: "Uszkodzony",
};

const TITLE_MAX = 75;
const TITLE_MIN = 12;
const TITLE_TARGET = 65;

interface PickedPhoto {
  fileName: string;
  mimeType: string;
  bytes: Uint8Array;
  previewUrl: string;
  sizeBytes: number;
}

/** Kolor licznika znaków wg stref z sekcji 7: czerwony / żółty / zielony. */
function titleZone(length: number): { color: string; hint: string } {
  if (length < TITLE_MIN || length > TITLE_MAX) {
    return {
      color: "text-coral",
      hint: `Allegro wymaga ${TITLE_MIN}-${TITLE_MAX} znaków.`,
    };
  }
  if (length < TITLE_TARGET) {
    return {
      color: "text-amber",
      hint: "Dodaj więcej atrybutów produktu, żeby wykorzystać limit znaków.",
    };
  }
  return { color: "text-teal-bright", hint: "Tytuł wykorzystuje limit znaków pod SEO." };
}

function NumberField({
  label,
  value,
  onChange,
  suffix = "zł",
  placeholder,
  min = 0,
  step = 0.01,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  suffix?: string;
  placeholder?: string;
  min?: number;
  step?: number;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[11.5px] text-slate-dim">{label}</span>
      <span className="relative flex items-center">
        <input
          type="number"
          inputMode="decimal"
          min={min}
          step={step}
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
          className="w-full rounded-[9px] border border-line bg-panel-2 px-3 py-2 pr-9 text-[12.5px] text-white outline-none transition-colors focus:border-teal-bright"
        />
        <span className="o-mono pointer-events-none absolute right-3 text-[10.5px] text-slate-dim">
          {suffix}
        </span>
      </span>
    </label>
  );
}

function PriceCard({
  breakdown,
  margin,
  onMarginChange,
}: {
  breakdown: OrdlakPriceBreakdown;
  margin: number;
  onMarginChange: (value: number) => void;
}) {
  const rows: [string, string][] = [
    ["Koszt zakupu", formatCurrency(breakdown.purchase_cost)],
    ["Sprowadzenie do siebie", formatCurrency(breakdown.inbound_shipping_cost)],
    ["Wysyłka do kupującego", formatCurrency(breakdown.buyer_shipping_cost)],
    [
      `Prowizja Allegro ${breakdown.commission_percent}% (od ceny + wysyłki)`,
      formatCurrency(breakdown.commission_amount),
    ],
  ];

  return (
    <div className="rounded-[11px] border border-line bg-panel-2 p-4">
      <SectionLabel>Kalkulacja ceny</SectionLabel>
      <div className="mt-3 flex flex-col gap-1.5">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-baseline justify-between gap-3">
            <span className="text-[12px] text-slate-dim">{label}</span>
            <span className="o-mono shrink-0 text-[12px] text-slate">{value}</span>
          </div>
        ))}
      </div>

      <div className="mt-3.5 border-t border-line pt-3.5">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-[12px] text-slate-dim">Marża docelowa</span>
          <span className="o-mono text-[12px] text-slate">{margin}%</span>
        </div>
        <input
          type="range"
          min={0}
          max={80}
          step={1}
          value={margin}
          onChange={(event) => onMarginChange(Number(event.target.value))}
          aria-label="Marża docelowa"
          className="mt-2 w-full accent-[var(--teal-bright)]"
        />
      </div>

      <div className="mt-3.5 flex items-baseline justify-between gap-3 border-t border-line pt-3.5">
        <span className="o-display text-[13px] font-semibold">Cena sugerowana</span>
        <span className="o-display text-[19px] font-semibold text-teal-bright">
          {formatCurrency(breakdown.suggested_price)}
        </span>
      </div>
    </div>
  );
}

export function OrdlakScreen() {
  const toast = useToast();
  const queryClient = useQueryClient();

  const [note, setNote] = React.useState("");
  const [condition, setCondition] = React.useState<OrdlakCondition>("new");
  const [purchaseCost, setPurchaseCost] = React.useState("");
  const [inboundShipping, setInboundShipping] = React.useState("0");
  const [buyerShipping, setBuyerShipping] = React.useState("0");
  const [commission, setCommission] = React.useState("");
  const [margin, setMargin] = React.useState(30);
  const [photos, setPhotos] = React.useState<PickedPhoto[]>([]);

  const [result, setResult] = React.useState<OrdlakGeneration | null>(null);
  const [titleDraft, setTitleDraft] = React.useState("");
  const [descriptionDraft, setDescriptionDraft] = React.useState("");
  const [tab, setTab] = React.useState<"wynik" | "historia">("wynik");
  const [preview, setPreview] = React.useState<OrdlakHistoryItem | null>(null);

  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const statusQuery = useQuery({
    queryKey: ["ordlak-status"],
    queryFn: async () => {
      const response = await window.ordly.ordlak.status();
      if (!response.ok) throw new Error(response.message);
      return response.data;
    },
  });

  const historyQuery = useQuery({
    queryKey: ["ordlak-history"],
    queryFn: async () => {
      const response = await window.ordly.ordlak.history(30);
      if (!response.ok) throw new Error(response.message);
      return response.data;
    },
  });

  const maxPhotos = statusQuery.data?.max_photos ?? 3;

  // Zwalnia obiekty URL miniatur przy odmontowaniu ekranu.
  //
  // Lista zdjec idzie przez ref, a efekt ma PUSTA liste zaleznosci celowo:
  // z `[photos]` React uruchamialby sprzatanie przy kazdym dodaniu zdjecia
  // i uniewaznialby URL-e miniatur, ktore wciaz sa na ekranie.
  const photosRef = React.useRef<PickedPhoto[]>([]);
  photosRef.current = photos;
  React.useEffect(
    () => () => {
      photosRef.current.forEach((photo) => URL.revokeObjectURL(photo.previewUrl));
    },
    []
  );

  const generateMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        note: note.trim(),
        condition,
        purchaseCost: Number(purchaseCost),
        inboundShippingCost: Number(inboundShipping || 0),
        buyerShippingCost: Number(buyerShipping || 0),
        commissionPercent: Number(commission),
        targetMarginPercent: margin,
        photos: photos.map<OrdlakPhotoPayload>((photo) => ({
          fileName: photo.fileName,
          mimeType: photo.mimeType,
          bytes: photo.bytes,
        })),
      };
      const response = await window.ordly.ordlak.generate(payload);
      if (!response.ok) throw new Error(response.message);
      return response.data;
    },
    onSuccess: (generation) => {
      setResult(generation);
      setTitleDraft(generation.title);
      setDescriptionDraft(generation.description_html);
      setMargin(generation.price_breakdown.target_margin_percent);
      setTab("wynik");
      setPreview(null);
      void queryClient.invalidateQueries({ queryKey: ["ordlak-history"] });
      toast.success("Oferta gotowa", "Sprawdź tytuł i opis przed skopiowaniem.");
    },
    onError: (error) => {
      toast.error(
        "Nie udało się wygenerować oferty",
        error instanceof Error ? error.message : "Spróbuj ponownie."
      );
    },
  });

  const finalizeMutation = useMutation({
    mutationFn: async () => {
      if (!result) throw new Error("Brak wygenerowanej oferty do zapisania.");
      const response = await window.ordly.ordlak.finalize({
        id: result.id,
        finalTitle: titleDraft,
        finalDescriptionHtml: descriptionDraft,
      });
      if (!response.ok) throw new Error(response.message);
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["ordlak-history"] });
      toast.success("Zapisano poprawki", "Historia pokazuje teraz Twoją wersję.");
    },
    onError: (error) => {
      toast.error(
        "Nie udało się zapisać poprawek",
        error instanceof Error ? error.message : "Spróbuj ponownie."
      );
    },
  });

  async function handlePickPhotos(event: React.ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (picked.length === 0) return;

    const room = maxPhotos - photos.length;
    if (room <= 0) {
      toast.error("Limit zdjęć", `Ordlak przyjmuje maksymalnie ${maxPhotos} zdjęcia.`);
      return;
    }

    const accepted: PickedPhoto[] = [];
    for (const file of picked.slice(0, room)) {
      const buffer = await file.arrayBuffer();
      accepted.push({
        fileName: file.name,
        mimeType: file.type || "image/jpeg",
        bytes: new Uint8Array(buffer),
        previewUrl: URL.createObjectURL(file),
        sizeBytes: file.size,
      });
    }
    setPhotos((current) => [...current, ...accepted]);

    if (picked.length > room) {
      toast.error("Limit zdjęć", `Dodano ${room} z ${picked.length} - limit to ${maxPhotos}.`);
    }
  }

  function removePhoto(index: number) {
    setPhotos((current) => {
      const removed = current[index];
      if (removed) URL.revokeObjectURL(removed.previewUrl);
      return current.filter((_, i) => i !== index);
    });
  }

  async function copyToClipboard(text: string, label: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Skopiowano", `${label} jest w schowku.`);
    } catch {
      toast.error("Nie udało się skopiować", "Schowek systemowy odmówił dostępu.");
    }
  }

  const canGenerate =
    note.trim().length > 0 &&
    purchaseCost.trim().length > 0 &&
    commission.trim().length > 0 &&
    !generateMutation.isPending;

  const livePrice = React.useMemo(() => {
    const source = result?.price_breakdown;
    if (!source) return null;
    return calculatePricePreview({
      purchaseCost: source.purchase_cost,
      inboundShippingCost: source.inbound_shipping_cost,
      buyerShippingCost: source.buyer_shipping_cost,
      commissionPercent: source.commission_percent,
      targetMarginPercent: margin,
    });
  }, [result, margin]);

  const pose: OrdlakPose = generateMutation.isPending
    ? "thinking"
    : result
      ? "happy"
      : "idle";

  const titleInfo = titleZone(titleDraft.length);
  const isEdited =
    result !== null &&
    (titleDraft !== result.title || descriptionDraft !== result.description_html);

  if (statusQuery.isError) {
    return (
      <ErrorState
        title="Nie udało się sprawdzić Ordlaka"
        detail={`Pi nie odpowiedziało na zapytanie o stan modułu. Jeśli widzisz 404, na Pi działa starsza wersja backendu - wgraj aktualizację i zrestartuj usługę ordly. ${
          statusQuery.error instanceof Error ? statusQuery.error.message : ""
        }`}
        onRetry={() => void statusQuery.refetch()}
      />
    );
  }

  return (
    <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,420px)_minmax(0,1fr)] overflow-hidden max-[1100px]:grid-cols-1 max-[1100px]:overflow-y-auto">
      {/* ------------------------------------------------ panel wejściowy */}
      <div className="flex min-h-0 flex-col gap-4 overflow-y-auto border-r border-line px-5 py-[18px]">
        {statusQuery.data && !statusQuery.data.configured && (
          <div className="flex items-start gap-2.5 rounded-[9px] border border-[rgba(255,133,99,.3)] bg-[rgba(255,133,99,.08)] px-3.5 py-3">
            <AlertIcon size={15} className="mt-0.5 shrink-0 text-coral" />
            <p className="text-[11.5px] leading-[1.6] text-slate">
              Ordlak nie ma klucza API. Uzupełnij{" "}
              <code className="o-mono text-slate">ANTHROPIC_API_KEY</code> w{" "}
              <code className="o-mono text-slate">~/ordly/backend/.env</code> na Pi i
              zrestartuj usługę:{" "}
              <code className="o-mono text-slate">sudo systemctl restart ordly</code>.
            </p>
          </div>
        )}

        <label className="flex flex-col gap-1.5">
          <span className="text-[11.5px] text-slate-dim">Notatka o produkcie</span>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={5}
            placeholder={
              "Marka i model, ilość w zestawie, pojemność/wymiary, materiał, " +
              "kolor, do czego służy.\n\nNp. ADBL Leather Kit - zestaw do skóry " +
              "samochodowej: Leather Cleaner 0,5 l, Leather Foamer 150 ml, " +
              "Conditioner 0,2 l, Mist 0,2 l, szczotka z drewnianym uchwytem, " +
              "mikrofibra. Nowy, w pudełku producenta."
            }
            className="resize-y rounded-[9px] border border-line bg-panel-2 px-3 py-2.5 text-[12.5px] leading-[1.6] text-white outline-none transition-colors focus:border-teal-bright"
          />
          <p className="text-[10.5px] leading-[1.5] text-slate-dim">
            Im więcej konkretów tu wpiszesz, tym bogatszy opis. Ordlak nie zmyśla
            parametrów, których nie podasz i których nie widać na zdjęciach.
          </p>
        </label>

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-[11.5px] text-slate-dim">Zdjęcia produktu</span>
            <span className="o-mono text-[10.5px] text-slate-dim">
              {photos.length}/{maxPhotos}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {photos.map((photo, index) => (
              <div
                key={`${photo.fileName}-${index}`}
                className="group relative h-[68px] w-[68px] overflow-hidden rounded-[9px] border border-line"
              >
                <img
                  src={photo.previewUrl}
                  alt={photo.fileName}
                  className="h-full w-full object-cover"
                />
                <button
                  onClick={() => removePhoto(index)}
                  aria-label={`Usuń zdjęcie ${photo.fileName}`}
                  className="absolute right-1 top-1 flex h-[19px] w-[19px] items-center justify-center rounded-md bg-[rgba(4,10,12,.78)] text-slate-dim opacity-0 transition-opacity hover:text-coral group-hover:opacity-100"
                >
                  <TrashIcon size={11} />
                </button>
              </div>
            ))}
            {photos.length < maxPhotos && (
              <button
                onClick={() => fileInputRef.current?.click()}
                className="flex h-[68px] w-[68px] flex-col items-center justify-center gap-1 rounded-[9px] border border-dashed border-line-strong text-[10.5px] text-slate-dim transition-colors hover:border-teal-bright hover:text-teal-bright"
              >
                <span className="text-[16px] leading-none">+</span>
                Dodaj
              </button>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            onChange={(event) => void handlePickPhotos(event)}
            className="hidden"
          />
          <p className="text-[10.5px] leading-[1.5] text-slate-dim">
            Zdjęcia trafiają tylko do modelu AI i nie są nigdzie zapisywane. Bez nich
            Ordlak nie oceni stanu produktu.
          </p>
        </div>

        <label className="flex flex-col gap-1.5">
          <span className="text-[11.5px] text-slate-dim">Stan produktu</span>
          <select
            value={condition}
            onChange={(event) => setCondition(event.target.value as OrdlakCondition)}
            className="rounded-[9px] border border-line bg-panel-2 px-3 py-2 text-[12.5px] text-white outline-none transition-colors focus:border-teal-bright"
          >
            {(Object.keys(CONDITION_LABEL) as OrdlakCondition[]).map((code) => (
              <option key={code} value={code}>
                {CONDITION_LABEL[code]}
              </option>
            ))}
          </select>
        </label>

        <div className="grid grid-cols-2 gap-3">
          <NumberField
            label="Koszt zakupu"
            value={purchaseCost}
            onChange={setPurchaseCost}
            placeholder="25.00"
          />
          <NumberField
            label="Sprowadzenie do siebie"
            value={inboundShipping}
            onChange={setInboundShipping}
          />
          <NumberField
            label="Wysyłka do kupującego"
            value={buyerShipping}
            onChange={setBuyerShipping}
          />
          <NumberField
            label="Prowizja Allegro"
            value={commission}
            onChange={setCommission}
            suffix="%"
            placeholder="10"
            step={0.1}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[11.5px] text-slate-dim">Marża docelowa</span>
            <span className="o-mono text-[11px] text-slate">{margin}%</span>
          </div>
          <input
            type="range"
            min={0}
            max={80}
            step={1}
            value={margin}
            onChange={(event) => setMargin(Number(event.target.value))}
            aria-label="Marża docelowa w formularzu"
            className="w-full accent-[var(--teal-bright)]"
          />
        </div>

        <Button
          onClick={() => generateMutation.mutate()}
          disabled={!canGenerate}
          icon={
            generateMutation.isPending ? (
              <RefreshIcon size={14} className="animate-spin-ring" />
            ) : undefined
          }
        >
          {generateMutation.isPending ? "Ordlak myśli…" : "Generuj ofertę"}
        </Button>
        {!canGenerate && !generateMutation.isPending && (
          <p className="-mt-2 text-[10.5px] leading-[1.5] text-slate-dim">
            Uzupełnij notatkę, koszt zakupu i prowizję Allegro.
          </p>
        )}
      </div>

      {/* --------------------------------------------------- panel wyniku */}
      <div className="flex min-h-0 flex-col overflow-hidden">
        <div className="flex items-center gap-2 border-b border-line px-[22px] py-[11px]">
          <Chip active={tab === "wynik"} onClick={() => setTab("wynik")}>
            Wynik
          </Chip>
          <Chip active={tab === "historia"} onClick={() => setTab("historia")}>
            Historia
          </Chip>
          {tab === "wynik" && result && (
            <div className="ml-auto">
              <MiniButton
                icon={
                  <RefreshIcon
                    size={13}
                    className={generateMutation.isPending ? "animate-spin-ring" : ""}
                  />
                }
                onClick={() => generateMutation.mutate()}
                disabled={!canGenerate}
              >
                Generuj ponownie
              </MiniButton>
            </div>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-[22px] py-[18px]">
          {tab === "historia" ? (
            <HistoryPanel
              query={historyQuery}
              selected={preview}
              onSelect={setPreview}
              onCopy={copyToClipboard}
            />
          ) : !result ? (
            <div className="flex h-full flex-col items-center justify-center gap-3.5 text-center">
              <OrdlakMascot pose={pose} size={104} />
              <h4 className="o-display text-[15px] font-semibold">
                {generateMutation.isPending ? "Ordlak pisze ofertę…" : "Ordlak czeka na produkt"}
              </h4>
              <p className="max-w-[340px] text-[12.5px] leading-[1.6] text-slate-dim">
                {generateMutation.isPending
                  ? "Analizuję notatkę i zdjęcia, żeby napisać tytuł pod SEO i opis zgodny z regulaminem."
                  : "Opisz produkt po lewej i dodaj zdjęcia. Dostaniesz gotowy tytuł, opis i wyliczoną cenę."}
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <div className="flex items-center gap-3">
                <OrdlakMascot pose={pose} size={54} floaty={false} />
                <div className="min-w-0">
                  <div className="o-display text-[14px] font-semibold">Oferta gotowa</div>
                  <div className="o-mono text-[10.5px] text-slate-dim">
                    {formatDateTime(result.created_at)} · {CONDITION_LABEL[result.condition]}
                    {result.photo_count > 0 && ` · ${result.photo_count} zdj.`}
                  </div>
                </div>
              </div>

              {/* ------------------------------------------------- tytuł */}
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between gap-3">
                  <SectionLabel>Tytuł oferty</SectionLabel>
                  <span className={`o-mono text-[10.5px] ${titleInfo.color}`}>
                    {titleDraft.length}/{TITLE_MAX}
                  </span>
                </div>
                <textarea
                  value={titleDraft}
                  onChange={(event) => setTitleDraft(event.target.value)}
                  rows={2}
                  className="resize-none rounded-[9px] border border-line bg-panel-2 px-3 py-2.5 text-[13px] leading-[1.5] text-white outline-none transition-colors focus:border-teal-bright"
                />
                <div className="flex items-center justify-between gap-3">
                  <p className={`text-[10.5px] leading-[1.5] ${titleInfo.color}`}>
                    {titleInfo.hint}
                  </p>
                  <MiniButton
                    icon={<ClipIcon size={12} />}
                    onClick={() => void copyToClipboard(titleDraft, "Tytuł")}
                  >
                    Kopiuj
                  </MiniButton>
                </div>
              </div>

              {/* -------------------------------------------------- opis */}
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between gap-3">
                  <SectionLabel>Opis oferty (HTML)</SectionLabel>
                  <MiniButton
                    icon={<ClipIcon size={12} />}
                    onClick={() => void copyToClipboard(descriptionDraft, "Opis")}
                  >
                    Kopiuj
                  </MiniButton>
                </div>
                <textarea
                  value={descriptionDraft}
                  onChange={(event) => setDescriptionDraft(event.target.value)}
                  rows={7}
                  className="o-mono resize-y rounded-[9px] border border-line bg-panel-2 px-3 py-2.5 text-[11.5px] leading-[1.65] text-white outline-none transition-colors focus:border-teal-bright"
                />
                <div className="rounded-[9px] border border-line bg-panel-2 px-3.5 py-3">
                  <div className="o-eyebrow mb-2">Podgląd</div>
                  <div
                    className="o-html-preview text-[12.5px] leading-[1.7] text-slate"
                    dangerouslySetInnerHTML={{ __html: sanitizeOfferHtml(descriptionDraft) }}
                  />
                </div>
              </div>

              {result.condition_notes && (
                <div className="rounded-[9px] border border-line bg-panel-2 px-3.5 py-3">
                  <div className="o-eyebrow mb-1.5">Ocena stanu ze zdjęć</div>
                  <p className="text-[12px] leading-[1.6] text-slate-dim">
                    {result.condition_notes}
                  </p>
                </div>
              )}

              {livePrice && (
                <PriceCard breakdown={livePrice} margin={margin} onMarginChange={setMargin} />
              )}

              <div className="flex items-center gap-2.5">
                <Button
                  variant="ghost"
                  onClick={() => finalizeMutation.mutate()}
                  disabled={!isEdited || finalizeMutation.isPending}
                  icon={<CheckIcon size={13} />}
                >
                  {finalizeMutation.isPending ? "Zapisuję…" : "Zapisz poprawki"}
                </Button>
                {!isEdited && (
                  <span className="text-[10.5px] text-slate-dim">
                    Zapisz, jeśli poprawisz tytuł lub opis.
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function HistoryPanel({
  query,
  selected,
  onSelect,
  onCopy,
}: {
  query: {
    isLoading: boolean;
    isError: boolean;
    error: unknown;
    data?: OrdlakHistoryItem[];
    refetch: () => void;
  };
  selected: OrdlakHistoryItem | null;
  onSelect: (item: OrdlakHistoryItem | null) => void;
  onCopy: (text: string, label: string) => Promise<void>;
}) {
  if (query.isLoading) return <SkeletonRows rows={4} />;

  if (query.isError) {
    return (
      <ErrorState
        title="Nie udało się pobrać historii"
        detail={`Pi nie odpowiedziało na zapytanie o historię generacji. ${
          query.error instanceof Error ? query.error.message : ""
        }`}
        onRetry={() => query.refetch()}
      />
    );
  }

  const items = query.data ?? [];

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3.5 px-6 py-14 text-center">
        <OrdlakMascot pose="idle" size={88} />
        <h4 className="o-display text-[15px] font-semibold">Jeszcze nic tu nie ma</h4>
        <p className="max-w-[300px] text-[12.5px] leading-[1.55] text-slate-dim">
          Każda wygenerowana oferta wyląduje tutaj razem z ceną i datą.
        </p>
      </div>
    );
  }

  if (selected) {
    return (
      <div className="flex flex-col gap-4">
        <MiniButton onClick={() => onSelect(null)}>← Wróć do listy</MiniButton>

        <div className="flex flex-col gap-1.5">
          <SectionLabel>Tytuł</SectionLabel>
          <p className="text-[13px] leading-[1.5] text-white">{selected.title}</p>
          <div className="flex items-center gap-2">
            <MiniButton
              icon={<ClipIcon size={12} />}
              onClick={() => void onCopy(selected.title, "Tytuł")}
            >
              Kopiuj tytuł
            </MiniButton>
            <MiniButton
              icon={<ClipIcon size={12} />}
              onClick={() => void onCopy(selected.description_html, "Opis")}
            >
              Kopiuj opis
            </MiniButton>
          </div>
        </div>

        <div className="rounded-[9px] border border-line bg-panel-2 px-3.5 py-3">
          <div className="o-eyebrow mb-2">Opis</div>
          <div
            className="o-html-preview text-[12.5px] leading-[1.7] text-slate"
            dangerouslySetInnerHTML={{ __html: sanitizeOfferHtml(selected.description_html) }}
          />
        </div>

        <div className="rounded-[9px] border border-line bg-panel-2 px-3.5 py-3">
          <div className="o-eyebrow mb-1.5">Notatka wejściowa</div>
          <p className="text-[12px] leading-[1.6] text-slate-dim">{selected.user_note}</p>
        </div>

        <div className="rounded-[11px] border border-line bg-panel-2 p-4">
          <SectionLabel>Cena z tej generacji</SectionLabel>
          <div className="mt-2.5 flex items-baseline justify-between">
            <span className="text-[12px] text-slate-dim">
              Marża {selected.price_breakdown.target_margin_percent}% · prowizja{" "}
              {selected.price_breakdown.commission_percent}%
            </span>
            <span className="o-display text-[17px] font-semibold text-teal-bright">
              {formatCurrency(selected.price_breakdown.suggested_price)}
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      {items.map((item) => (
        <button
          key={item.id}
          onClick={() => onSelect(item)}
          className="flex flex-col gap-1 border-b border-line px-1 py-3 text-left transition-colors hover:bg-panel-2"
        >
          <span className="flex items-center gap-2">
            <b className="truncate text-[12.5px] font-semibold">{item.title}</b>
            <span className="o-mono ml-auto shrink-0 text-[11px] text-teal-bright">
              {formatCurrency(item.price_breakdown.suggested_price)}
            </span>
          </span>
          <span className="o-mono flex items-center gap-2 text-[10px] text-slate-dim">
            {formatDateTime(item.created_at)} · {CONDITION_LABEL[item.condition]}
            {item.is_edited && <span className="text-amber">· poprawiona ręcznie</span>}
          </span>
        </button>
      ))}
    </div>
  );
}
