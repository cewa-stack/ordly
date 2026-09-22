/**
 * Liczba, ktora przelicza sie do nowej wartosci (0,4 s) zamiast skakac -
 * 1:1 z `mobile/src/components/CountUp.tsx`.
 *
 * Po synchronizacji widac, CO sie zmienilo, bez porownywania w pamieci.
 * Przy `prefers-reduced-motion` wartosc zmienia sie od razu.
 */
import * as React from "react";

const DURATION_MS = 400;

function reducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function CountUp({
  value,
  format = (v) => String(Math.round(v)),
}: {
  value: number;
  format?: (value: number) => string;
}) {
  const [shown, setShown] = React.useState(value);
  const current = React.useRef(value);

  React.useEffect(() => {
    const start = current.current;
    if (start === value || reducedMotion()) {
      current.current = value;
      setShown(value);
      return;
    }
    let frame = 0;
    const t0 = performance.now();
    const step = (now: number) => {
      const k = Math.min(1, (now - t0) / DURATION_MS);
      const next = start + (value - start) * (1 - Math.pow(1 - k, 3));
      current.current = next;
      setShown(next);
      if (k < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [value]);

  return <>{format(shown)}</>;
}
