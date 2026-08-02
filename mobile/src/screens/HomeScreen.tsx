/**
 * Dashboard — §4 specyfikacji. Kolejność sekcji = kolejność pytań
 * sprzedawcy: (1) czy coś nowego? → KPI, (2) czy wszystko działa? →
 * status sync, (3) jak idzie? → wykres, (4) co muszę zrobić? → alerty.
 */
import * as React from "react";
import {
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useQueryClient } from "@tanstack/react-query";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { AlertIcon, GearIcon, ReceiptIcon, TruckIcon } from "@/icons";
import { useDashboard, useOrders, useStock } from "@/api/hooks";
import type { Order, StockItem } from "@/api/types";
import { HeroSalesCard, HeroSalesCardSkeleton } from "@/components/HeroSalesCard";
import { StatCard } from "@/components/StatCard";
import { SyncStatusRow } from "@/components/SyncStatusRow";
import { OrderRow } from "@/components/OrderRow";
import { StockRow } from "@/components/StockRow";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Skeleton } from "@/components/Skeleton";
import type { RootStackParamList } from "@/navigation/types";

const TODAY_LABEL = new Intl.DateTimeFormat("pl-PL", {
  weekday: "long",
  day: "numeric",
  month: "long",
}).format(new Date());

function greetingForHour(hour: number): string {
  if (hour < 5) return "Dobrej nocy";
  if (hour < 12) return "Dzień dobry";
  if (hour < 18) return "Miłego dnia";
  return "Dobry wieczór";
}

export function HomeScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const queryClient = useQueryClient();
  const dashboard = useDashboard();
  const orders = useOrders(0);
  const stock = useStock();

  const [refreshing, setRefreshing] = React.useState(false);

  async function onRefresh() {
    setRefreshing(true);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      queryClient.invalidateQueries({ queryKey: ["orders"] }),
      queryClient.invalidateQueries({ queryKey: ["stock"] }),
    ]);
    setRefreshing(false);
  }

  const recentOrders: Order[] = (orders.data ?? []).slice(0, 3);
  const lowStock: StockItem[] = (stock.data ?? [])
    .filter((item: StockItem) => item.status !== "ok")
    .slice(0, 3);

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor={colors.primary}
        />
      }
    >
      <View style={styles.topbar}>
        <View style={styles.topbarLeft}>
          <Text style={styles.greeting}>{greetingForHour(new Date().getHours())}</Text>
          <Text style={styles.dateLabel}>
            {TODAY_LABEL.charAt(0).toUpperCase() + TODAY_LABEL.slice(1)}
          </Text>
        </View>
        <Pressable
          style={({ pressed }) => [styles.iconButton, pressed && styles.iconButtonPressed]}
          onPress={() => navigation.navigate("Settings")}
          hitSlop={8}
        >
          <GearIcon size={18} color={colors.textSecondary} />
        </Pressable>
      </View>

      {dashboard.isPending ? (
        <HeroSalesCardSkeleton />
      ) : dashboard.isError || !dashboard.data ? (
        <ErrorState
          message="Nie udało się pobrać danych dashboardu"
          onRetry={() => dashboard.refetch()}
        />
      ) : (
        <>
          <HeroSalesCard
            revenueToday={dashboard.data.revenue_today}
            ordersToday={dashboard.data.orders_today}
            ordersToShip={dashboard.data.orders_to_ship}
            trendPercent={dashboard.data.trend_percent}
            series={dashboard.data.revenue_last_7_days}
          />

          <View style={styles.statPair}>
            <StatCard
              icon={<ReceiptIcon size={16} color={colors.textSecondary} />}
              label="Zamówienia dziś"
              value={String(dashboard.data.orders_today)}
            />
            <StatCard
              icon={<TruckIcon size={16} color={colors.textSecondary} />}
              label="Do wysłania"
              value={String(dashboard.data.orders_to_ship)}
              valueColor={dashboard.data.orders_to_ship > 0 ? colors.warning : undefined}
            />
          </View>

          <SyncStatusRow
            lastSyncHuman={dashboard.data.last_sync_human}
            marketplaceConnectionOk={dashboard.data.marketplace_connection_ok}
          />
        </>
      )}

      {lowStock.length > 0 ? (
        <>
          <View style={styles.sectionHead}>
            <View style={styles.sectionTitleRow}>
              <AlertIcon size={16} color={colors.warning} />
              <Text style={styles.sectionTitle}>Wymaga uwagi</Text>
            </View>
            <Text
              style={styles.sectionLink}
              onPress={() => navigation.navigate("Main", { screen: "Stock" })}
            >
              magazyn
            </Text>
          </View>
          {lowStock.map((item: StockItem) => (
            <StockRow
              key={item.sku}
              item={item}
              onPress={() => navigation.navigate("StockItem", { sku: item.sku })}
            />
          ))}
        </>
      ) : null}

      <View style={styles.sectionHead}>
        <Text style={styles.sectionTitle}>Ostatnie zamówienia</Text>
        <Text
          style={styles.sectionLink}
          onPress={() => navigation.navigate("Main", { screen: "Orders" })}
        >
          wszystkie
        </Text>
      </View>
      {orders.isPending ? (
        <Skeleton height={88} radius={radii.lg} style={{ marginBottom: spacing.sm }} />
      ) : orders.isError ? (
        <ErrorState onRetry={() => orders.refetch()} />
      ) : recentOrders.length === 0 ? (
        <EmptyState
          mascotPose="orders"
          title="Czekamy na pierwsze zamówienie"
          description="Nowe zamówienia z Allegro pojawią się tutaj automatycznie."
        />
      ) : (
        recentOrders.map((order: Order) => (
          <OrderRow
            key={order.external_id}
            order={order}
            onPress={() => navigation.navigate("OrderDetail", { externalId: order.external_id })}
          />
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    paddingBottom: 110,
  },
  topbar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.lg,
  },
  topbarLeft: {
    flexShrink: 1,
  },
  greeting: {
    ...typography.headline,
    color: colors.text,
  },
  dateLabel: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 1,
  },
  iconButton: {
    width: 40,
    height: 40,
    borderRadius: radii.full,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  iconButtonPressed: {
    backgroundColor: colors.surfaceRaised,
  },
  statPair: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.md,
  },
  sectionHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: spacing.xl,
    marginBottom: spacing.md,
  },
  sectionTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  sectionTitle: {
    ...typography.sectionTitle,
    color: colors.text,
  },
  sectionLink: {
    ...typography.caption,
    fontSize: 13,
    fontWeight: "600",
    color: colors.primary,
  },
});
