/**
 * Karta zamówienia — §5 specyfikacji: wiersz 1 marketplace + nr (mono),
 * badge statusu po prawej; wiersz 2 kupujący SemiBold; wiersz 3 liczba
 * produktów · data, kwota Bold po prawej. Kupujący i kwota mają największą
 * wagę typograficzną (dane decyzyjne), numer celowo trzeciorzędny.
 */
import * as React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import type { Order } from "@/api/types";
import { formatMoney, fulfillmentLabel, plural } from "@/utils/format";
import { StatusBadge } from "./StatusBadge";

interface OrderRowProps {
  order: Order;
  onPress?: () => void;
}

function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pl-PL", { day: "numeric", month: "short" });
}

export function OrderRow({ order, onPress }: OrderRowProps) {
  const label = fulfillmentLabel(order.fulfillment_status);
  const count = order.products.length;
  const productsLabel = `${count} ${plural(count, "produkt", "produkty", "produktów")}`;

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      <View style={styles.row}>
        <Text style={styles.id} numberOfLines={1}>
          {order.marketplace} · #{order.external_id}
        </Text>
        <StatusBadge label={label} />
      </View>
      <Text style={styles.buyer} numberOfLines={1}>
        {order.buyer_login}
      </Text>
      <View style={styles.row}>
        <Text style={styles.meta} numberOfLines={1}>
          {productsLabel} · {shortDate(order.order_date)}
        </Text>
        <Text style={styles.amount}>{formatMoney(order.total_amount, order.currency)}</Text>
      </View>
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
    gap: 4,
  },
  pressed: {
    opacity: 0.85,
    backgroundColor: colors.surfaceRaised,
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
  buyer: {
    ...typography.calloutSemibold,
    fontSize: 16,
    color: colors.text,
  },
  meta: {
    ...typography.footnote,
    color: colors.textSecondary,
    flexShrink: 1,
  },
  amount: {
    ...typography.rowAmount,
    color: colors.text,
  },
});
