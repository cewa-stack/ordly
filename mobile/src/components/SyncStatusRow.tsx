/**
 * Mikro-status synchronizacji — §4.1: kropka (success = zsynchronizowano /
 * danger = problem) + tekst. Jedyny sygnał "czy wszystko działa" na
 * ekranie Start poza kartami KPI.
 */
import * as React from "react";
import { StyleSheet, Text, View } from "react-native";

import { colors } from "@/theme/colors";
import { spacing, typography } from "@/theme/typography";

interface SyncStatusRowProps {
  lastSyncHuman: string;
  marketplaceConnectionOk: boolean;
}

export function SyncStatusRow({
  lastSyncHuman,
  marketplaceConnectionOk,
}: SyncStatusRowProps) {
  const dotColor = marketplaceConnectionOk ? colors.success : colors.danger;
  return (
    <View style={styles.row}>
      <View style={[styles.dot, { backgroundColor: dotColor }]} />
      <Text style={styles.text}>
        {marketplaceConnectionOk ? "Synchronizacja z Allegro: " : "Problem z połączeniem · ostatni sync: "}
        <Text style={styles.bold}>{lastSyncHuman}</Text>
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.sm,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  text: {
    ...typography.caption,
    color: colors.textSecondary,
    flexShrink: 1,
  },
  bold: {
    color: colors.text,
    fontWeight: "600",
  },
});
