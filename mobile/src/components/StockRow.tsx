/**
 * Karta produktu magazynowego — §7 specyfikacji: nazwa SemiBold, SKU mono,
 * po prawej stan Bold + pasek zapasu w trzech kolorach
 * (success > próg · warning niski · danger zero/krytyczny).
 * Odpowiedź na "czy mam towar" bez czytania.
 *
 * Pasek pojawia się TYLKO wtedy, gdy jest do czego porównać stan
 * (`max_stock` albo `min_stock`) - patrz `stockRatio`. Gdy produkt nie ma
 * żadnego progu, informację o stanie niesie sam licznik sztuk, dlatego
 * jest tu większy niż globalna `typography.statValue`.
 */
import * as React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, stockStatusColor } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import type { StockItem } from "@/api/types";
import { AlertIcon } from "@/icons";

interface StockRowProps {
  item: StockItem;
  onPress?: () => void;
}

/**
 * Proporcja wypełnienia paska zapasu albo `null`, gdy nie ma jej z czego policzyć.
 *
 * Kolejność mianowników jest od najdokładniejszego do najsłabszego:
 * `max_stock` to stan docelowy ustawiony przez użytkownika, więc
 * `stock / max_stock` jest jedyną proporcją, która naprawdę coś znaczy.
 * Bez niego zostaje przybliżenie „pełno = dwa razy próg alertu”.
 *
 * `null` (brak obu progów) NIE jest tym samym co zero i nie jest tym
 * samym co pełno. Poprzednia wersja zwracała w tym miejscu `1`, przez co
 * produkt z 5 sztukami i produkt z 5000 sztuk miały identyczny, pełny
 * pasek - a próg alertu jest polem OPCJONALNYM, więc dotyczyło to
 * większości magazynu. Pasek przestawał nieść jakąkolwiek informację
 * o stanie, co przy przewijaniu listy wyglądało jak jego nieczytelność.
 */
function stockRatio(item: StockItem): number | null {
  if (item.max_stock !== null && item.max_stock > 0) {
    return item.stock / item.max_stock;
  }
  if (item.min_stock > 0) {
    return item.stock / (item.min_stock * 2);
  }
  return item.stock === 0 ? 0 : null;
}

export function StockRow({ item, onPress }: StockRowProps) {
  const ratio = stockRatio(item);
  const barColor = stockStatusColor[item.status];
  const isLow = item.status !== "ok";
  // Bez punktu odniesienia pasek nie ma czego pokazać, więc go nie ma -
  // rysowanie go „na jakąś szerokość” tylko udawałoby informację.
  // Wtedy sam licznik sztuk mówi o stanie wszystko, co da się powiedzieć.
  const width =
    ratio === null
      ? null
      : (`${Math.max(4, Math.min(100, Math.round(ratio * 100)))}%` as const);

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      <View style={styles.main}>
        <View style={styles.info}>
          <Text style={styles.name} numberOfLines={1}>
            {item.name}
          </Text>
          <Text style={styles.sku}>{item.sku}</Text>
        </View>
        <View style={styles.stockBlock}>
          {/* Licznik przejmuje kolor statusu, bo to on - a nie pasek
              szeroki na 60 px - rzuca się w oczy przy przewijaniu listy. */}
          <Text style={[styles.qty, isLow && { color: barColor }]}>
            {item.stock} <Text style={styles.qtyUnit}>szt.</Text>
          </Text>
          {width !== null ? (
            <View style={styles.bar}>
              <View style={[styles.barFill, { width, backgroundColor: barColor }]} />
            </View>
          ) : null}
        </View>
      </View>
      {isLow ? (
        <View style={styles.lowFlag}>
          <AlertIcon size={12} color={colors.warning} />
          <Text style={styles.lowFlagText}>
            {item.stock === 0 ? "brak towaru — zamów dostawę" : "poniżej minimum — zamów dostawę"}
          </Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    padding: spacing.lg,
    marginBottom: spacing.sm,
  },
  pressed: {
    opacity: 0.85,
    backgroundColor: colors.surfaceRaised,
  },
  main: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.md,
  },
  info: {
    flex: 1,
    minWidth: 0,
  },
  name: {
    ...typography.calloutSemibold,
    color: colors.text,
  },
  sku: {
    ...typography.mono,
    fontSize: 12,
    color: colors.textDim,
    marginTop: 2,
  },
  stockBlock: {
    alignItems: "flex-end",
    gap: 6,
  },
  qty: {
    // Lokalny wariant `typography.statValue` (18/700): na karcie
    // magazynowej liczba sztuk jest głównym nośnikiem stanu, bo pasek
    // bywa nieobecny (patrz `stockRatio`). Globalnej `statValue` nie
    // ruszamy - używa jej m.in. pasek KPI na innych ekranach.
    ...typography.statValue,
    fontSize: 21,
    lineHeight: 27,
    color: colors.text,
  },
  qtyUnit: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  bar: {
    width: 60,
    height: 4,
    borderRadius: radii.full,
    backgroundColor: colors.surfaceRaised,
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: radii.full,
  },
  lowFlag: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: spacing.sm,
  },
  lowFlagText: {
    ...typography.caption,
    color: colors.warning,
  },
});
