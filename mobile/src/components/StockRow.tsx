/**
 * Karta produktu magazynowego — §7 specyfikacji: nazwa SemiBold, SKU mono,
 * po prawej stan Bold 20 + pasek zapasu w trzech kolorach
 * (success > próg · warning niski · danger zero/krytyczny).
 * Odpowiedź na "czy mam towar" bez czytania.
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

export function StockRow({ item, onPress }: StockRowProps) {
  const ratio = item.min_stock > 0 ? item.stock / (item.min_stock * 2) : item.stock > 0 ? 1 : 0;
  const width = `${Math.max(4, Math.min(100, Math.round(ratio * 100)))}%` as const;
  const barColor = stockStatusColor[item.status];
  const isLow = item.status !== "ok";

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
          <Text style={styles.qty}>
            {item.stock} <Text style={styles.qtyUnit}>szt.</Text>
          </Text>
          <View style={styles.bar}>
            <View style={[styles.barFill, { width, backgroundColor: barColor }]} />
          </View>
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
    ...typography.statValue,
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
