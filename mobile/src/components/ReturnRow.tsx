/**
 * Karta zwrotu — analogiczna do OrderRow: nr zwrotu + status, kupujący,
 * produkty, zamówienie źródłowe i data. Tylko do odczytu (bez akcji -
 * decyzje o zwrotach zapadają w Allegro albo na desktopie).
 */
import * as React from "react";
import { StyleSheet, Text, View } from "react-native";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import type { ReturnItem } from "@/api/types";

function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pl-PL", { day: "numeric", month: "short" });
}

interface ReturnRowProps {
  item: ReturnItem;
}

export function ReturnRow({ item }: ReturnRowProps) {
  return (
    <View style={styles.card}>
      <View style={styles.row}>
        <Text style={styles.id} numberOfLines={1}>
          {item.marketplace} · #{item.external_id}
        </Text>
        <View style={styles.statusPill}>
          <Text style={styles.statusText} numberOfLines={1}>
            {item.status}
          </Text>
        </View>
      </View>
      <Text style={styles.buyer} numberOfLines={1}>
        {item.buyer_login}
      </Text>
      <Text style={styles.meta} numberOfLines={2}>
        {item.products_summary}
      </Text>
      <View style={styles.row}>
        <Text style={styles.orderRef} numberOfLines={1}>
          Zamówienie #{item.order_external_id}
        </Text>
        <Text style={styles.date}>{shortDate(item.return_date)}</Text>
      </View>
    </View>
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
    gap: 4,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
  },
  id: {
    ...typography.mono,
    color: colors.textSecondary,
    flexShrink: 1,
  },
  statusPill: {
    height: 22,
    borderRadius: radii.full,
    paddingHorizontal: 9,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceRaised,
  },
  statusText: {
    ...typography.caption,
    fontSize: 10,
    color: colors.textSecondary,
  },
  buyer: {
    ...typography.calloutSemibold,
    fontSize: 15,
    color: colors.text,
  },
  meta: {
    ...typography.footnote,
    color: colors.textSecondary,
  },
  orderRef: {
    ...typography.footnote,
    color: colors.textDim,
    flexShrink: 1,
  },
  date: {
    ...typography.caption,
    fontSize: 11,
    color: colors.textDim,
  },
});
