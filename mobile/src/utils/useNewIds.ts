/**
 * Które pozycje pojawiły się na liście od poprzedniego odświeżenia.
 *
 * Pierwsze dane tylko zapamiętujemy - otwarcie ekranu nie ma migać
 * wszystkim naraz. Każde następne pojawienie się nowego `id` (po
 * synchronizacji albo po odświeżeniu w tle) zwraca je w zbiorze, a wiersz
 * raz mignie akcentem. Dzięki temu nie trzeba porównywać listy w pamięci.
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
    // Zależność to `key`, nie `ids`: tablica jest nowa przy każdym
    // renderze, a `key` zmienia się tylko razem z jej zawartością.
  }, [key]);

  return fresh;
}
