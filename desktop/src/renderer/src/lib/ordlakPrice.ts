/**
 * Kalkulacja ceny po stronie renderera - WYLACZNIE do podgladu na zywo
 * przy ruszaniu suwakiem marzy.
 *
 * To celowa duplikacja wzoru z `backend/src/app/services/ordlak_service.py`
 * (`calculate_price`). Alternatywa - zapytanie do backendu na kazdy ruch
 * suwaka - oznaczalaby setki zadan HTTP przy jednym przeciagnieciu, a to
 * czysta arytmetyka bez udzialu AI. Zrodlem prawdy pozostaje backend:
 * wartosc zapisana w historii zawsze pochodzi z niego.
 *
 * WAZNE przy zmianach: prowizja Allegro liczy sie od sumy
 * `cena + koszt wysylki do kupujacego`, nie od samej ceny. Kazda zmiana
 * tego wzoru musi isc rownolegle w obu plikach.
 */
import type { OrdlakPriceBreakdown } from "../types/api";

export interface PriceInputs {
  purchaseCost: number;
  inboundShippingCost: number;
  buyerShippingCost: number;
  commissionPercent: number;
  targetMarginPercent: number;
}

/** Zwraca `null`, gdy prowizja + marza >= 100% (backend odrzuci taki zestaw). */
export function calculatePricePreview(inputs: PriceInputs): OrdlakPriceBreakdown | null {
  const {
    purchaseCost,
    inboundShippingCost,
    buyerShippingCost,
    commissionPercent,
    targetMarginPercent,
  } = inputs;

  const denominator = 1 - commissionPercent / 100 - targetMarginPercent / 100;
  if (denominator <= 0) return null;

  const numerator =
    purchaseCost + inboundShippingCost + (commissionPercent / 100) * buyerShippingCost;
  const suggestedPrice = round2(numerator / denominator);
  const commissionAmount = round2((commissionPercent / 100) * (suggestedPrice + buyerShippingCost));

  return {
    purchase_cost: purchaseCost,
    inbound_shipping_cost: inboundShippingCost,
    buyer_shipping_cost: buyerShippingCost,
    commission_percent: commissionPercent,
    target_margin_percent: targetMarginPercent,
    commission_amount: commissionAmount,
    suggested_price: suggestedPrice,
  };
}

function round2(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}
