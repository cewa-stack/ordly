/**
 * Trwałe przechowywanie hurtowni i historii zamówień do nich - dane
 * czysto lokalne/prywatne użytkownika (nie sekrety), więc zwykły JSON
 * w katalogu userData wystarcza (bez szyfrowania jak w tokenStore.ts).
 */
import { app } from "electron";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { randomUUID } from "node:crypto";

/** Pozycja asortymentu hurtowni - nazwa i ilosc, ktora zwykle sie bierze. */
export interface WholesalerItem {
  name: string;
  quantity: number;
}

export interface Wholesaler {
  id: string;
  name: string;
  email: string;
  contactPerson?: string;
  items: WholesalerItem[];
  /** Przypisany szablon maila; brak = szablon domyslny. */
  templateId?: string;
}

/**
 * Szablon maila do hurtowni. Dwa warianty, bo mail bez pozycji (pytanie
 * o cennik, termin) nie moze zaczynac sie od "chcialbym zamowic".
 */
export interface WholesalerTemplate {
  id: string;
  name: string;
  subject: string;
  body: string;
  inquirySubject: string;
  inquiryBody: string;
  isDefault: boolean;
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

function templatesFilePath(): string {
  return join(app.getPath("userData"), "wholesaler_templates.json");
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

/**
 * Plik na dysku moze pochodzic z wersji, w ktorej hurtownia trzymala
 * `linkedSkus` wskazujace na produkty magazynowe. Tamtych produktow juz
 * nie ma, a lista pozycji jest teraz wlasnoscia hurtowni - stara zawartosc
 * czytamy jako puste pozycje zamiast wywracac ekran na `undefined.length`.
 */
function normalizeWholesaler(raw: Wholesaler): Wholesaler {
  const items = Array.isArray(raw.items) ? raw.items : [];
  return {
    ...raw,
    items: items
      .filter((item) => typeof item?.name === "string" && item.name.trim().length > 0)
      .map((item) => ({
        name: item.name,
        quantity: Number.isFinite(item.quantity) ? Math.max(1, Math.trunc(item.quantity)) : 1,
      })),
  };
}

export function listWholesalers(): Wholesaler[] {
  return readJsonArray<Wholesaler>(wholesalersFilePath()).map(normalizeWholesaler);
}

export function saveWholesaler(input: Omit<Wholesaler, "id"> & { id?: string }): Wholesaler {
  const wholesalers = listWholesalers();
  if (input.id) {
    const index = wholesalers.findIndex((w) => w.id === input.id);
    if (index >= 0) {
      const updated: Wholesaler = { ...wholesalers[index], ...input, id: input.id };
      // Formularz edycji zawsze wysyla wybor szablonu; "domyslny" przychodzi
      // jako brak pola, a samo pominiecie w spreadzie zostawiloby stary wybor.
      if (!input.templateId) delete updated.templateId;
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

/**
 * Szablon, ktory zastepuje dawny, wpisany w kod. Przy pierwszym uruchomieniu
 * trafia do pliku jako domyslny, wiec maile wygladaja jak dotad, dopoki
 * uzytkownik sam czegos nie zmieni.
 */
const BUILT_IN_TEMPLATE: Omit<WholesalerTemplate, "id"> = {
  name: "Standardowe zamówienie",
  subject: "Zamówienie - {produkty}",
  body: `Dzień dobry {osoba_kontaktowa},

Chciałbym złożyć zamówienie na następujące produkty:

{lista_pozycji}

Proszę o potwierdzenie dostępności i przewidywanego terminu dostawy.

Pozdrawiam`,
  inquirySubject: "Zapytanie",
  inquiryBody: `Dzień dobry {osoba_kontaktowa},

`,
  isDefault: true,
};

function asText(value: unknown, fallback: string): string {
  return typeof value === "string" ? value : fallback;
}

/** Zawsze co najmniej jeden szablon i dokladnie jeden domyslny. */
export function listWholesalerTemplates(): WholesalerTemplate[] {
  const raw = readJsonArray<Partial<WholesalerTemplate>>(templatesFilePath());
  const templates: WholesalerTemplate[] = raw
    .filter((t) => typeof t?.id === "string" && typeof t.name === "string")
    .map((t) => ({
      id: t.id as string,
      name: t.name as string,
      subject: asText(t.subject, BUILT_IN_TEMPLATE.subject),
      body: asText(t.body, BUILT_IN_TEMPLATE.body),
      inquirySubject: asText(t.inquirySubject, BUILT_IN_TEMPLATE.inquirySubject),
      inquiryBody: asText(t.inquiryBody, BUILT_IN_TEMPLATE.inquiryBody),
      isDefault: t.isDefault === true,
    }));

  if (templates.length === 0) {
    const seeded = [{ ...BUILT_IN_TEMPLATE, id: randomUUID() }];
    writeJsonArray(templatesFilePath(), seeded);
    return seeded;
  }

  const defaultIndex = Math.max(
    0,
    templates.findIndex((t) => t.isDefault)
  );
  return templates.map((t, i) => ({ ...t, isDefault: i === defaultIndex }));
}

export function saveWholesalerTemplate(
  input: Omit<WholesalerTemplate, "id" | "isDefault"> & { id?: string }
): WholesalerTemplate {
  const templates = listWholesalerTemplates();
  const fields = {
    name: input.name,
    subject: input.subject,
    body: input.body,
    inquirySubject: input.inquirySubject,
    inquiryBody: input.inquiryBody,
  };
  const index = input.id ? templates.findIndex((t) => t.id === input.id) : -1;
  let saved: WholesalerTemplate;
  if (index >= 0) {
    saved = { ...templates[index], ...fields };
    templates[index] = saved;
  } else {
    saved = { ...fields, id: randomUUID(), isDefault: false };
    templates.push(saved);
  }
  writeJsonArray(templatesFilePath(), templates);
  return saved;
}

export function setDefaultWholesalerTemplate(id: string): void {
  const templates = listWholesalerTemplates();
  if (!templates.some((t) => t.id === id)) {
    throw new Error("Ten szablon już nie istnieje.");
  }
  writeJsonArray(
    templatesFilePath(),
    templates.map((t) => ({ ...t, isDefault: t.id === id }))
  );
}

/**
 * Domyslnego nie da sie usunac - hurtownie bez przypisania musza miec
 * z czego zlozyc maila. Hurtownie przypisane do usuwanego szablonu
 * wracaja do domyslnego.
 */
export function deleteWholesalerTemplate(id: string): void {
  const templates = listWholesalerTemplates();
  const target = templates.find((t) => t.id === id);
  if (!target) return;
  if (target.isDefault) {
    throw new Error("Nie można usunąć szablonu domyślnego. Najpierw ustaw inny jako domyślny.");
  }
  writeJsonArray(
    templatesFilePath(),
    templates.filter((t) => t.id !== id)
  );

  const wholesalers = listWholesalers();
  if (wholesalers.some((w) => w.templateId === id)) {
    writeJsonArray(
      wholesalersFilePath(),
      wholesalers.map((w) => {
        if (w.templateId !== id) return w;
        const copy = { ...w };
        delete copy.templateId;
        return copy;
      })
    );
  }
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
