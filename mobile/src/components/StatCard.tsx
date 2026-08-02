/**
 * Karta KPI — §4.2: liczba Bold z cyframi tabelarycznymi, label pod spodem,
 * radius 16-18, tło surface z borderem.
 */
import * as React from "react";
import { StyleSheet, Text, View } from "react-native";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";

interface StatCardProps {
  icon?: React.ReactNode;
  label: string;
  value: string;
  valueColor?: string;
}

export function StatCard({ icon, label, value, valueColor }: StatCardProps) {
  return (
    <View style={styles.card}>
      <View style={styles.top}>
        {icon}
        <Text style={styles.label} numberOfLines={1}>
          {label}
        </Text>
      </View>
      <Text style={[styles.value, valueColor ? { color: valueColor } : null]} numberOfLines={1}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    padding: spacing.lg,
  },
  top: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  label: {
    ...typography.footnote,
    color: colors.textSecondary,
    flexShrink: 1,
  },
  value: {
    ...typography.statValue,
    color: colors.text,
    marginTop: spacing.sm,
  },
});
