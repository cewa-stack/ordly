/**
 * Postep synchronizacji na karcie powitalnej - ten sam pasek i ten sam
 * rytm co na telefonie (`mobile/src/screens/StartScreen.tsx`), zeby obie
 * aplikacje mowily jednym jezykiem. Wczesniej desktop tylko krecil ikonka.
 *
 * Pi nie raportuje postepu, wiec pasek jest uczciwie niepewny: szybko do
 * 70%, potem pelznie ku 94%, a do 100% domyka go dopiero odpowiedz.
 * Nieudana synchronizacja gasnie tam, gdzie stanela.
 *
 * Wartosci ida prosto do stylu elementu (bez stanu Reacta) - 60 klatek
 * na sekunde nie ma przerysowywac calego ekranu Start.
 */
import * as React from "react";
import type { SyncPhase } from "../lib/sync";

const outCubic = (x: number) => 1 - Math.pow(1 - x, 3);
const outQuad = (x: number) => 1 - (1 - x) * (1 - x);
const linear = (x: number) => x;

export function SyncSweep({ phase }: { phase: SyncPhase }) {
  const ref = React.useRef<HTMLDivElement>(null);
  const progress = React.useRef(0);
  const opacity = React.useRef(0);

  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let cancelled = false;
    let frame = 0;
    const timers: number[] = [];

    const paint = () => {
      el.style.transform = `translateX(${((progress.current - 1) * 100).toFixed(2)}%)`;
      el.style.opacity = opacity.current.toFixed(3);
    };
    const tween = (
      target: React.MutableRefObject<number>,
      to: number,
      ms: number,
      ease: (x: number) => number
    ) =>
      new Promise<void>((resolve) => {
        if (reduce || ms === 0) {
          target.current = to;
          paint();
          resolve();
          return;
        }
        const from = target.current;
        const t0 = performance.now();
        const step = (now: number) => {
          if (cancelled) return resolve();
          const k = Math.min(1, (now - t0) / ms);
          target.current = from + (to - from) * ease(k);
          paint();
          if (k < 1) frame = requestAnimationFrame(step);
          else resolve();
        };
        frame = requestAnimationFrame(step);
      });
    const wait = (ms: number) =>
      new Promise<void>((resolve) => timers.push(window.setTimeout(resolve, reduce ? 0 : ms)));

    void (async () => {
      if (phase === "working") {
        progress.current = 0;
        opacity.current = 1;
        paint();
        await tween(progress, 0.7, 1400, outCubic);
        if (!cancelled) await tween(progress, 0.94, 14000, outQuad);
      } else if (phase === "success") {
        // Razem 1620 ms - miesci sie w fazie sukcesu (1900 ms w lib/sync).
        await tween(progress, 1, 320, outCubic);
        if (!cancelled) await wait(700);
        if (!cancelled) await tween(opacity, 0, 600, linear);
      } else {
        // Spoczynek: po sukcesie pasek juz zgasl, po porazce gasnie teraz.
        await tween(opacity, 0, 260, linear);
      }
    })();

    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      timers.forEach((id) => window.clearTimeout(id));
    };
  }, [phase]);

  return (
    <div
      ref={ref}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 z-0"
      style={{ transform: "translateX(-100%)", opacity: 0 }}
    >
      {/* Wypelnienie gestnieje ku czolu - wiadomo, w ktora strone idzie. */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(90deg, color-mix(in srgb, var(--teal) 3%, transparent), color-mix(in srgb, var(--teal) 12%, transparent))",
        }}
      />
      <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-teal" />
    </div>
  );
}
