/**
 * Karta hero "Przychód dziś" — §4.2/§10 specyfikacji: jedyna karta
 * z akcentem koloru (subtelny teal w tle), kwota Display Bold,
 * wykres liniowy 7 dni z wypełnieniem gradientowym primary → transparent.
 */
import * as React from "react";
import { StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Defs, LinearGradient, Path, Stop } from "react-native-svg";
import { LinearGradient as ExpoLinearGradient } from "expo-linear-gradient";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { TrendUpIcon } from "@/icons";
import { formatMoney, plural } from "@/utils/format";
import { Skeleton } from "./Skeleton";

interface HeroSalesCardProps {
  revenueToday: number;
  ordersToday: number;
  ordersToShip: number;
  trendPercent: number | null;
  series: number[];
}

const SPARK_WIDTH = 280;
const SPARK_HEIGHT = 56;

/** Wykres liniowy z wypełnieniem gradientowym, rysowany z realnych danych API. */
function AreaSparkline({ values }: { values: number[] }) {
  if (values.length < 2) {
    return null;
  }
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const step = SPARK_WIDTH / (values.length - 1);
  const inset = 4;
  const usable = SPARK_HEIGHT - inset * 2;

  const points = values.map((value, index) => {
    const x = index * step;
    const y = inset + (usable - ((value - min) / range) * usable);
    return { x, y };
  });

  const line = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(" ");
  const area = `${line} L${SPARK_WIDTH},${SPARK_HEIGHT} L0,${SPARK_HEIGHT} Z`;
  const last = points[points.length - 1];

  return (
    <Svg width="100%" height={SPARK_HEIGHT} viewBox={`0 0 ${SPARK_WIDTH} ${SPARK_HEIGHT}`}>
      <Defs>
        <LinearGradient id="heroFill" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={colors.primary} stopOpacity={0.28} />
          <Stop offset="1" stopColor={colors.primary} stopOpacity={0} />
        </LinearGradient>
      </Defs>
      <Path d={area} fill="url(#heroFill)" />
      <Path
        d={line}
        fill="none"
        stroke={colors.primary}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Circle cx={last.x} cy={last.y} r={3.5} fill={colors.primary} />
    </Svg>
  );
}

export function HeroSalesCard({
  revenueToday,
  ordersToday,
  ordersToShip,
  trendPercent,
  series,
}: HeroSalesCardProps) {
  const trendUp = (trendPercent ?? 0) >= 0;
  return (
    <View style={styles.card}>
      <ExpoLinearGradient
        colors={[colors.primaryTint, "transparent"]}
        start={{ x: 0.1, y: 0 }}
        end={{ x: 0.7, y: 0.9 }}
        style={StyleSheet.absoluteFillObject}
        pointerEvents="none"
      />
      <View style={styles.topRow}>
        <View>
          <Text style={styles.label}>Przychód dziś</Text>
          <Text style={styles.value}>{formatMoney(revenueToday)}</Text>
        </View>
        {trendPercent !== null ? (
          <View
            style={[
              styles.trend,
              { backgroundColor: trendUp ? colors.successTint : colors.dangerTint },
            ]}
          >
            <View style={!trendUp && styles.trendIconDown}>
              <TrendUpIcon size={11} color={trendUp ? colors.success : colors.danger} />
            </View>
            <Text
              style={[styles.trendLabel, { color: trendUp ? colors.success : colors.danger }]}
            >
              {trendUp ? "+" : ""}
              {trendPercent.toFixed(0)}%
            </Text>
          </View>
        ) : null}
      </View>

      <View style={styles.sparkWrap}>
        <AreaSparkline values={series} />
      </View>

      <Text style={styles.description}>
        {ordersToday} {plural(ordersToday, "zamówienie", "zamówienia", "zamówień")} dziś
        {ordersToShip > 0
          ? ` · ${ordersToShip} ${ordersToShip === 1 ? "czeka" : "czekają"} na wysyłkę`
          : " · wszystko wysłane"}
      </Text>
    </View>
  );
}

export function HeroSalesCardSkeleton() {
  return (
    <View style={styles.card}>
      <Skeleton height={14} width="40%" style={{ marginBottom: spacing.sm }} />
      <Skeleton height={34} width="60%" style={{ marginBottom: spacing.md }} />
      <Skeleton height={SPARK_HEIGHT} />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.xl,
    padding: spacing.lg,
    overflow: "hidden",
  },
  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  label: {
    ...typography.footnote,
    color: colors.textSecondary,
  },
  value: {
    ...typography.display,
    color: colors.text,
    marginTop: 2,
  },
  trend: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    height: 24,
    paddingHorizontal: 9,
    borderRadius: radii.full,
  },
  trendIconDown: {
    transform: [{ rotate: "180deg" }],
  },
  trendLabel: {
    ...typography.badgeLabel,
  },
  sparkWrap: {
    marginTop: spacing.md,
  },
  description: {
    ...typography.footnote,
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
});
