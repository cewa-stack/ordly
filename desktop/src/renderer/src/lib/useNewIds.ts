/**
 * Ktore pozycje pojawily sie na liscie od poprzedniego odswiezenia -
 * 1:1 z `mobile/src/utils/useNewIds.ts`.
 *
 * Pierwsze dane tylko zapamietujemy - otwarcie ekranu nie ma migac
 * wszystkim naraz. Kazde nastepne pojawienie sie nowego `id` zwraca je
 * w zbiorze, a wiersz raz mignie akcentem (`.o-row-flash`).
 */
import * as React from "react";

export function useNewIds(ids: string[] | undefined): Set<string> {
  const seen = React.useRef<Set<string> | null>(null);
  const [fresh, setFresh] = React.useState<Set<string>>(() => new Set());
  const key = ids?.join("|");

  React.useEffect(() => {
    if (!ids) return;
    if (seen.current === null) {
      seen.current = new Set(ids);
      return;
    }
    const known = seen.current;
    const added = ids.filter((id) => !known.has(id));
    ids.forEach((id) => known.add(id));
    if (added.length > 0) setFresh(new Set(added));
    // Zaleznosc to `key`, nie `ids`: tablica jest nowa przy kazdym
    // renderze, a `key` zmienia sie tylko razem z jej zawartoscia.
  }, [key]);

  return fresh;
}
