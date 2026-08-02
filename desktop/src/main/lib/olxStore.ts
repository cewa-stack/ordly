/**
 * Lokalne przechowywanie ofert OLX (Wariant B - brak potwierdzonego,
 * gotowego do uzycia dostepu do API OLX, patrz appplans_05 sekcja 6).
 *
 * Dane czysto lokalne/rachunkowe uzytkownika - zwykly JSON w katalogu
 * userData, bez szyfrowania (jak wholesalerStore.ts), NIE bierze
 * udzialu w zadnym automatycznym cyklu synchronizacji z backendem.
 */
import { app } from "electron";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { randomUUID } from "node:crypto";

export interface OlxOffer {
  id: string;
  title: string;
  price: number;
  stock: number;
  url: string;
  linkedSku?: string;
}

function filePath(): string {
  return join(app.getPath("userData"), "olx_offers.json");
}

function readAll(): OlxOffer[] {
  if (!existsSync(filePath())) {
    return [];
  }
  try {
    const parsed = JSON.parse(readFileSync(filePath(), "utf-8"));
    return Array.isArray(parsed) ? (parsed as OlxOffer[]) : [];
  } catch {
    return [];
  }
}

function writeAll(items: OlxOffer[]): void {
  writeFileSync(filePath(), JSON.stringify(items, null, 2), "utf-8");
}

export function listOlxOffers(): OlxOffer[] {
  return readAll();
}

export function saveOlxOffer(input: Omit<OlxOffer, "id"> & { id?: string }): OlxOffer {
  const offers = readAll();
  if (input.id) {
    const index = offers.findIndex((o) => o.id === input.id);
    if (index >= 0) {
      const updated: OlxOffer = { ...offers[index], ...input, id: input.id };
      offers[index] = updated;
      writeAll(offers);
      return updated;
    }
  }
  const created: OlxOffer = { ...input, id: randomUUID() };
  offers.push(created);
  writeAll(offers);
  return created;
}

export function deleteOlxOffer(id: string): void {
  writeAll(readAll().filter((o) => o.id !== id));
}
