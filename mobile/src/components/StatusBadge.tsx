/**
 * Badge statusowy (pastylka) — §15.10: wys. 24 pt, radius pełny,
 * tło = kolor statusu przy 12% krycia, tekst 12 pt SemiBold w pełnym
 * kolorze statusu. Podwójne kodowanie (kolor + tekst) = czytelne również
 * przy daltonizmie.
 */
import * as React from "react";
import { StyleSheet, Text, View } from "react-native";

import { colors, orderStatusColor, orderStatusTint } from "@/theme/colors";
import { radii, typography } from "@/theme/typography";

interface StatusBadgeProps {
  label: string;
}

export function StatusBadge({ label }: StatusBadgeProps) {
  const color = orderStatusColor[label] ?? colors.textSecondary;
  const tint = orderStatusTint[label] ?? colors.surfaceRaised;
  return (
    <View style={[styles.badge, { backgroundColor: tint }]}>
      <Text style={[styles.label, { color }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    height: 24,
    borderRadius: radii.full,
    paddingHorizontal: 10,
    alignItems: "center",
    justifyContent: "center",
    alignSelf: "flex-start",
  },
  label: {
    ...typography.badgeLabel,
  },
});
