/**
 * Szczegóły zamówienia — §6 specyfikacji: karta hero (badge + kwota),
 * pionowy timeline statusów (Nowe → Pakowanie → Wysłane), produkty
 * z podsumowaniem "Razem", przesyłka na żądanie ("Sprawdź status" —
 * jak /tracking w bocie, nigdy automatycznie).
 */
import * as React from "react";
import { Animated, Easing, ScrollView, StyleSheet, Text, View } from "react-native";
import { useRoute, type RouteProp } from "@react-navigation/native";

import { colors, orderStatusColor } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { useOrder, useOrderTracking } from "@/api/hooks";
import { ApiError } from "@/api/client";
import { ErrorState } from "@/components/ErrorState";
import { PrimaryButton } from "@/components/PrimaryButton";
import { Skeleton } from "@/components/Skeleton";
import { StatusBadge } from "@/components/StatusBadge";
import { CheckIcon, TruckIcon } from "@/icons";
import type { OrderProduct } from "@/api/types";
import { formatDate, formatMoney, fulfillmentLabel } from "@/utils/format";
import type { RootStackParamList } from "@/navigation/types";

const TIMELINE_STAGES = ["Nowe", "Pakowanie", "Wysłane"] as const;

/** Pulsujący pierścień wokół bieżącego etapu - jedyny "żywy" akcent na
 *  ekranie poza maskotką (której tu celowo nie ma, §15.16). */
function PulsingRing() {
  const scale = React.useRef(new Animated.Value(0.7)).current;
  const opacity = React.useRef(new Animated.Value(0.5)).current;

  React.useEffect(() => {
    const loop = Animated.loop(
      Animated.parallel([
        Animated.timing(scale, {
          toValue: 1.7,
          duration: 1600,
          easing: Easing.out(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(opacity, {
          toValue: 0,
          duration: 1600,
          easing: Easing.out(Easing.ease),
          useNativeDriver: true,
        }),
      ])
    );
    loop.start();
    return () => {
      loop.stop();
      scale.setValue(0.7);
      opacity.setValue(0.5);
    };
  }, [opacity, scale]);

  return (
    <Animated.View
      style={[styles.pulsingRing, { opacity, transform: [{ scale }] }]}
    />
  );
}

/** Pionowa oś statusów: ukończone = wypełniony węzeł z ptaszkiem,
 *  bieżący = pierścień primary z pulsem, przyszłe = pusty border. */
function StatusTimeline({ label }: { label: string }) {
  const currentIndex = TIMELINE_STAGES.indexOf(label as (typeof TIMELINE_STAGES)[number]);
  if (currentIndex < 0) {
    return null;
  }
  return (
    <View style={styles.timeline}>
      {TIMELINE_STAGES.map((stage, index) => {
        const done = index < currentIndex;
        const current = index === currentIndex;
        return (
          <View key={stage} style={styles.timelineRow}>
            <View style={styles.timelineRail}>
              <View
                style={[
                  styles.timelineNode,
                  done && styles.timelineNodeDone,
                  current && styles.timelineNodeCurrent,
                ]}
              >
                {current ? <PulsingRing /> : null}
                {done ? <CheckIcon size={12} color={colors.onPrimary} /> : null}
                {current ? <View style={styles.timelineNodeDot} /> : null}
              </View>
              {index < TIMELINE_STAGES.length - 1 ? (
                <View
                  style={[styles.timelineLine, done && styles.timelineLineDone]}
                />
              ) : null}
            </View>
            <Text
              style={[
                styles.timelineLabel,
                (done || current) && styles.timelineLabelActive,
              ]}
            >
              {stage}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

export function OrderDetailScreen() {
  const route = useRoute<RouteProp<RootStackParamList, "OrderDetail">>();
  const { externalId } = route.params;
  const order = useOrder(externalId);
  const tracking = useOrderTracking();

  if (order.isPending) {
    return (
      <View style={styles.screen}>
        <Skeleton height={180} radius={radii.xl} style={{ margin: spacing.xl }} />
      </View>
    );
  }

  if (order.isError || !order.data) {
    return (
      <View style={styles.screen}>
        <ErrorState message="Nie znaleziono zamówienia" onRetry={() => order.refetch()} />
      </View>
    );
  }

  const data = order.data;
  const label = fulfillmentLabel(data.fulfillment_status);
  const statusColor = orderStatusColor[label] ?? colors.textSecondary;
  const productsTotal = data.products.reduce(
    (sum: number, product: OrderProduct) => sum + Number(product.total_price || 0),
    0
  );

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <View style={styles.heroCard}>
        <View style={styles.topRow}>
          <Text style={styles.orderId}>
            {data.marketplace} · #{data.external_id}
          </Text>
          <StatusBadge label={label} />
        </View>
        <Text style={styles.amount}>{formatMoney(data.total_amount, data.currency)}</Text>

        {label === "Anulowane" ? (
          <View style={styles.cancelledNote}>
            <Text style={styles.cancelledNoteText}>Zamówienie zostało anulowane.</Text>
          </View>
        ) : (
          <StatusTimeline label={label} />
        )}

        <View style={styles.metaBlock}>
          <View style={styles.metaRow}>
            <Text style={styles.metaLabel}>Kupujący</Text>
            <Text style={styles.metaValue}>{data.buyer_login}</Text>
          </View>
          <View style={styles.metaRow}>
            <Text style={styles.metaLabel}>Data zamówienia</Text>
            <Text style={styles.metaValue}>{formatDate(data.order_date)}</Text>
          </View>
          <View style={[styles.metaRow, styles.metaRowLast]}>
            <Text style={styles.metaLabel}>Marketplace</Text>
            <Text style={styles.metaValue}>{data.marketplace}</Text>
          </View>
        </View>
      </View>

      <Text style={styles.sectionTitle}>Produkty</Text>
      <View style={styles.card}>
        {data.products.map((product: OrderProduct, index: number) => (
          <View
            key={product.external_id + index}
            style={[styles.productRow, index === 0 && styles.productRowFirst]}
          >
            <View style={styles.productInfo}>
              <Text style={styles.productName} numberOfLines={2}>
                {product.name}
              </Text>
              <Text style={styles.productMeta}>
                {product.quantity} szt. × {formatMoney(product.unit_price, data.currency)}
              </Text>
            </View>
            <Text style={styles.productTotal}>
              {formatMoney(product.total_price, data.currency)}
            </Text>
          </View>
        ))}
        <View style={styles.totalRow}>
          <Text style={styles.totalLabel}>Razem</Text>
          <Text style={styles.totalValue}>{formatMoney(productsTotal, data.currency)}</Text>
        </View>
      </View>

      <Text style={styles.sectionTitle}>Przesyłka</Text>
      <View style={styles.card}>
        {tracking.isError ? (
          <>
            <Text style={styles.trackingError}>
              {tracking.error instanceof ApiError
                ? tracking.error.message
                : "Nie udało się pobrać statusu przesyłki"}
            </Text>
            <PrimaryButton
              label="Spróbuj ponownie"
              onPress={() => tracking.mutate(data.external_id)}
              loading={tracking.isPending}
            />
          </>
        ) : tracking.data ? (
          <>
            <Text style={styles.trackingStatus}>{tracking.data.status ?? "Brak danych"}</Text>
            {tracking.data.carrier ? (
              <Text style={styles.trackingMeta}>{tracking.data.carrier}</Text>
            ) : null}
            {tracking.data.tracking_number ? (
              <Text style={styles.trackingNumber}>{tracking.data.tracking_number}</Text>
            ) : null}
          </>
        ) : (
          <PrimaryButton
            label="Sprawdź status przesyłki"
            icon={<TruckIcon size={16} color={colors.onPrimary} />}
            onPress={() => tracking.mutate(data.external_id)}
            loading={tracking.isPending}
          />
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.xl,
    paddingBottom: 60,
  },
  heroCard: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.xl,
    padding: spacing.lg,
  },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    padding: spacing.lg,
  },
  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
  },
  orderId: {
    ...typography.mono,
    color: colors.textSecondary,
    flexShrink: 1,
  },
  amount: {
    ...typography.display,
    fontSize: 30,
    lineHeight: 36,
    color: colors.text,
    marginTop: spacing.sm,
  },
  cancelledNote: {
    backgroundColor: colors.dangerTint,
    borderRadius: radii.sm,
    padding: spacing.md,
    marginTop: spacing.lg,
  },
  cancelledNoteText: {
    ...typography.footnote,
    color: colors.danger,
  },
  timeline: {
    marginTop: spacing.lg,
  },
  timelineRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.md,
  },
  timelineRail: {
    alignItems: "center",
    width: 24,
  },
  timelineNode: {
    width: 24,
    height: 24,
    borderRadius: radii.full,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  timelineNodeDone: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  timelineNodeCurrent: {
    borderColor: colors.primary,
  },
  timelineNodeDot: {
    width: 8,
    height: 8,
    borderRadius: radii.full,
    backgroundColor: colors.primary,
  },
  pulsingRing: {
    position: "absolute",
    width: 24,
    height: 24,
    borderRadius: radii.full,
    borderWidth: 2,
    borderColor: colors.primary,
  },
  timelineLine: {
    width: 2,
    height: 20,
    backgroundColor: colors.border,
    marginVertical: 2,
  },
  timelineLineDone: {
    backgroundColor: colors.primary,
  },
  timelineLabel: {
    ...typography.footnote,
    color: colors.textDim,
    paddingTop: 3,
  },
  timelineLabelActive: {
    color: colors.text,
    fontWeight: "600",
  },
  metaBlock: {
    marginTop: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  metaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  metaRowLast: {
    borderBottomWidth: 0,
    paddingBottom: 0,
  },
  metaLabel: {
    ...typography.footnote,
    color: colors.textSecondary,
  },
  metaValue: {
    ...typography.footnote,
    fontWeight: "600",
    color: colors.text,
  },
  sectionTitle: {
    ...typography.sectionTitle,
    color: colors.text,
    marginTop: spacing.xl,
    marginBottom: spacing.md,
  },
  productRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: spacing.md,
    paddingVertical: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  productRowFirst: {
    borderTopWidth: 0,
    paddingTop: 0,
  },
  productInfo: {
    flex: 1,
    minWidth: 0,
  },
  productName: {
    ...typography.callout,
    fontWeight: "500",
    color: colors.text,
  },
  productMeta: {
    ...typography.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  productTotal: {
    ...typography.mono,
    fontSize: 15,
    color: colors.text,
  },
  totalRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  totalLabel: {
    ...typography.calloutSemibold,
    color: colors.text,
  },
  totalValue: {
    ...typography.rowAmount,
    color: colors.text,
  },
  trackingStatus: {
    ...typography.calloutSemibold,
    color: colors.text,
  },
  trackingMeta: {
    ...typography.footnote,
    color: colors.textSecondary,
    marginTop: 4,
  },
  trackingNumber: {
    ...typography.mono,
    color: colors.textSecondary,
    marginTop: 2,
  },
  trackingError: {
    ...typography.footnote,
    color: colors.danger,
    marginBottom: spacing.md,
  },
});
