/**
 * Liczba, która przelicza się do nowej wartości (0,4 s) zamiast skakać.
 *
 * Po synchronizacji widać, CO się zmieniło - „Wartość dziś” podjeżdża
 * z 179 do 228 zł - bez porównywania w pamięci. Przy wyłączonych
 * animacjach systemu wartość zmienia się od razu.
 */
import * as React from "react";
import { Text, type StyleProp, type TextStyle } from "react-native";

import { useTheme } from "@/theme/theme";

const DURATION_MS = 400;

interface CountUpProps {
  value: number;
  format?: (value: number) => string;
  style?: StyleProp<TextStyle>;
  numberOfLines?: number;
}

export function CountUp({
  value,
  format = (v) => String(Math.round(v)),
  style,
  numberOfLines,
}: CountUpProps) {
  const { reduceMotion } = useTheme();
  const [shown, setShown] = React.useState(value);
  const current = React.useRef(value);

  React.useEffect(() => {
    const start = current.current;
    if (start === value || reduceMotion) {
      current.current = value;
      setShown(value);
      return;
    }
    let frame = 0;
    const t0 = Date.now();
    const step = () => {
      const k = Math.min(1, (Date.now() - t0) / DURATION_MS);
      const next = start + (value - start) * (1 - Math.pow(1 - k, 3));
      current.current = next;
      setShown(next);
      if (k < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [value, reduceMotion]);

  return (
    <Text style={style} numberOfLines={numberOfLines}>
      {format(shown)}
    </Text>
  );
}
