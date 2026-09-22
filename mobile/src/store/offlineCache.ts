/**
 * Ostatni stan danych w pamięci telefonu - na wypadek, gdy telefon nie
 * widzi Pi (Tailscale wyłączony, słaby zasięg).
 *
 * Bez tego aplikacja otwarta bez połączenia pokazywała same błędy. Teraz
 * startuje z ostatnio pobranym stanem, a pasek `OfflineBanner` mówi
 * wprost, z której godziny on jest. W trybie bez połączenia nic nie da
 * się zmienić - tylko podejrzeć.
 *
 * Działa w PWA (`localStorage`). Na natywnym iOS/Androidzie nie ma tu
 * magazynu na większe dane (SecureStore jest na klucze), więc tam zapis
 * jest wyłączony, a pasek i tak mówi o braku połączenia.
 *
 * Bez nowych bibliotek: `dehydrate`/`hydrate` to część react-query.
 */
import { Platform } from "react-native";
import { dehydrate, hydrate, type QueryClient } from "@tanstack/react-query";

const STORAGE_KEY = "ordly.cache.v1";
/** Starszy stan nie jest już „ostatnim stanem”, tylko wprowadza w błąd. */
const MAX_AGE_MS = 7 * 24 * 60 * 60_000;
/** localStorage ma ok. 5 MB na całą stronę - zostawiamy zapas na token. */
const MAX_BYTES = 2_000_000;
const SAVE_DEBOUNCE_MS = 2_000;

/**
 * Co warto mieć bez połączenia. Bez treści maili (duże, a i tak otwiera
 * się je w Gmailu), dziennika zdarzeń i stanu push - to nie „stan sklepu”.
 */
const PERSISTED = new Set([
  "dashboard",
  "orders",
  "order",
  "issues",
  "issue-messages",
  "returns",
  "offers",
  "mail-messages",
  "reply-templates",
]);

const enabled = (): boolean => Platform.OS === "web" && typeof localStorage !== "undefined";

/** Wczytuje zapisany stan do cache - wołane raz, przed pierwszym renderem. */
export function restoreOfflineCache(client: QueryClient): void {
  if (!enabled()) return;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw) as { savedAt: number; state: unknown };
    if (!saved?.state || Date.now() - saved.savedAt > MAX_AGE_MS) {
      localStorage.removeItem(STORAGE_KEY);
      return;
    }
    hydrate(client, saved.state);
  } catch {
    // Uszkodzony zapis nie może wywrócić startu - zaczynamy od zera.
  }
}

/**
 * Zapisuje stan po każdej zmianie danych (z opóźnieniem, żeby seria
 * odświeżeń w tle nie zapisywała się dziesięć razy). Zwraca funkcję
 * wyłączającą zapis.
 */
export function persistOfflineCache(client: QueryClient): () => void {
  if (!enabled()) return () => {};
  let timer: ReturnType<typeof setTimeout> | null = null;

  const save = () => {
    timer = null;
    try {
      const state = dehydrate(client, {
        shouldDehydrateQuery: (query) =>
          query.state.status === "success" && PERSISTED.has(String(query.queryKey[0])),
      });
      const raw = JSON.stringify({ savedAt: Date.now(), state });
      if (raw.length > MAX_BYTES) return;
      localStorage.setItem(STORAGE_KEY, raw);
    } catch {
      // Pełny albo zablokowany localStorage (tryb prywatny) - trudno,
      // aplikacja działa dalej, tylko bez stanu na później.
    }
  };

  const unsubscribe = client.getQueryCache().subscribe((event) => {
    if (event.type !== "updated" || event.action.type !== "success") return;
    if (timer) clearTimeout(timer);
    timer = setTimeout(save, SAVE_DEBOUNCE_MS);
  });

  return () => {
    unsubscribe();
    if (timer) clearTimeout(timer);
  };
}

/** Wylogowanie czyści zapisany stan - to dane kupujących. */
export function clearOfflineCache(): void {
  if (!enabled()) return;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // brak dostępu do localStorage - nie ma czego czyścić
  }
}
