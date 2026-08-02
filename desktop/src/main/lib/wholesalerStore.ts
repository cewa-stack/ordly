/**
 * Trwałe przechowywanie hurtowni i historii zamówień do nich - dane
 * czysto lokalne/prywatne użytkownika (nie sekrety), więc zwykły JSON
 * w katalogu userData wystarcza (bez szyfrowania jak w tokenStore.ts).
 */
import { app } from "electron";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { randomUUID } from "node:crypto";

export interface Wholesaler {
  id: string;
  name: string;
  email: string;
  contactPerson?: string;
  linkedSkus: string[];
}

export interface WholesalerOrderRecord {
  id: string;
  wholesalerId: string;
  wholesalerName: string;
  sentAt: string;
  subject: string;
  itemsSummary: string;
}

function wholesalersFilePath(): string {
  return join(app.getPath("userData"), "wholesalers.json");
}

function historyFilePath(): string {
  return join(app.getPath("userData"), "wholesaler_orders.json");
}

function readJsonArray<T>(path: string): T[] {
  if (!existsSync(path)) {
    return [];
  }
  try {
    const parsed = JSON.parse(readFileSync(path, "utf-8"));
    return Array.isArray(parsed) ? (parsed as T[]) : [];
  } catch {
    return [];
  }
}

function writeJsonArray<T>(path: string, items: T[]): void {
  writeFileSync(path, JSON.stringify(items, null, 2), "utf-8");
}

export function listWholesalers(): Wholesaler[] {
  return readJsonArray<Wholesaler>(wholesalersFilePath());
}

export function saveWholesaler(input: Omit<Wholesaler, "id"> & { id?: string }): Wholesaler {
  const wholesalers = listWholesalers();
  if (input.id) {
    const index = wholesalers.findIndex((w) => w.id === input.id);
    if (index >= 0) {
      const updated: Wholesaler = { ...wholesalers[index], ...input, id: input.id };
      wholesalers[index] = updated;
      writeJsonArray(wholesalersFilePath(), wholesalers);
      return updated;
    }
  }
  const created: Wholesaler = { ...input, id: randomUUID() };
  wholesalers.push(created);
  writeJsonArray(wholesalersFilePath(), wholesalers);
  return created;
}

export function deleteWholesaler(id: string): void {
  const remaining = listWholesalers().filter((w) => w.id !== id);
  writeJsonArray(wholesalersFilePath(), remaining);
}

export function listOrderHistory(): WholesalerOrderRecord[] {
  return readJsonArray<WholesalerOrderRecord>(historyFilePath()).sort((a, b) =>
    b.sentAt.localeCompare(a.sentAt)
  );
}

export function appendOrderHistory(record: Omit<WholesalerOrderRecord, "id">): void {
  const history = readJsonArray<WholesalerOrderRecord>(historyFilePath());
  history.push({ ...record, id: randomUUID() });
  writeJsonArray(historyFilePath(), history);
}
