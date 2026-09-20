/**
 * Karta zwrotu — analogiczna do OrderRow: nr zwrotu + status, kupujący,
 * produkty, zamówienie źródłowe i data. Tylko do odczytu (bez akcji -
 * decyzje o zwrotach zapadają w Allegro albo na desktopie).
 */
import * as React from "react";
import { StyleSheet, Text, View } from "react-native";

import type { Palette } from "@/theme/colors";
import { useThemedStyles } from "@/theme/theme";
import { radii, spacing, typography } from "@/theme/typography";
import { parseApiDate, returnStatusLabel } from "@/utils/format";
import type { ReturnItem } from "@/api/types";

function shortDate(iso: string): string {
  return parseApiDate(iso).toLocaleDateString("pl-PL", { day: "numeric", month: "short" });
}

interface ReturnRowProps {
  item: ReturnItem;
}

export function ReturnRow({ item }: ReturnRowProps) {
  const styles = useThemedStyles(createStyles);
  return (
    <View style={styles.card}>
      <View style={styles.row}>
        <Text style={styles.id} numberOfLines={1}>
          {item.marketplace} · #{item.external_id}
        </Text>
        <View style={styles.statusPill}>
          <Text style={styles.statusText} numberOfLines={1}>
            {returnStatusLabel(item.status)}
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

const createStyles = (c: Palette) =>
  StyleSheet.create({
  card: {
    backgroundColor: c.card,
    borderWidth: 1,
    borderColor: c.line,
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
    color: c.tx2,
    flexShrink: 1,
  },
  statusPill: {
    height: 22,
    borderRadius: radii.full,
    paddingHorizontal: 9,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: c.card2,
  },
  statusText: {
    ...typography.caption,
    fontSize: 10,
    color: c.tx2,
  },
  buyer: {
    ...typography.calloutSemibold,
    fontSize: 15,
    color: c.tx,
  },
  meta: {
    ...typography.footnote,
    color: c.tx2,
  },
  orderRef: {
    ...typography.footnote,
    color: c.tx3,
    flexShrink: 1,
  },
  date: {
    ...typography.caption,
    fontSize: 11,
    color: c.tx3,
  },
});
