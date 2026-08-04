/**
 * Zamówienia - zakładka podglądu wg sekcji 6.2 specyfikacji.
 *
 * ZMIANA: zniknął lokalny przycisk "Synchronizuj" i komunikat o wyniku.
 * Synchronizacja mieszka teraz w pigułce we wspólnym nagłówku, bo wg
 * sekcji 1 i 6.1 to JEDYNE działanie w aplikacji mobilnej - pięć jego
 * kopii na pięciu ekranach przeczyło tej regule.
 *
 * Podczas synchronizacji treść zakładki zastępuje skeleton (sekcja 6.3
 * pkt 3), a koniec listy mówi wprost, gdzie wykonać akcję (sekcja 7.4).
 */
import * as React from "react";
import { FlatList, RefreshControl, StyleSheet, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useQueryClient } from "@tanstack/react-query";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { useOrders, useSearchOrders } from "@/api/hooks";
import { OrderRow } from "@/components/OrderRow";
import { SearchBar } from "@/components/SearchBar";
import { FilterChip } from "@/components/FilterChip";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Skeleton } from "@/components/Skeleton";
import { ReceiptIcon } from "@/icons";
import { TabHeading } from "@/components/TabHeading";
import { ListEndNote } from "@/components/ListEndNote";
import { useSync } from "@/store/sync";
import { fulfillmentLabel } from "@/utils/format";
import type { Order } from "@/api/types";
import type { RootStackParamList } from "@/navigation/types";

const STATUS_FILTERS = ["Wszystkie", "Nowe", "Pakowanie", "Wysłane", "Anulowane"] as const;
type StatusFilter = (typeof STATUS_FILTERS)[number];

export function OrdersScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const queryClient = useQueryClient();
  const [query, setQuery] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState<StatusFilter>("Wszystkie");
  const isSearching = query.trim().length > 0;

  const ordersQuery = useOrders(0);
  const searchQuery = useSearchOrders(query);
  const { isBusy, sync } = useSync();

  const baseData = isSearching ? searchQuery.data : ordersQuery.data;
  const isPending = isSearching ? searchQuery.isPending : ordersQuery.isPending;
  const isError = isSearching ? searchQuery.isError : ordersQuery.isError;

  const counts = React.useMemo(() => {
    const map: Record<StatusFilter, number> = {
      Wszystkie: baseData?.length ?? 0,
      Nowe: 0,
      Pakowanie: 0,
      Wysłane: 0,
      Anulowane: 0,
    };
    for (const order of baseData ?? []) {
      const label = fulfillmentLabel(order.fulfillment_status) as StatusFilter;
      if (label in map) {
        map[label] += 1;
      }
    }
    return map;
  }, [baseData]);

  const data = React.useMemo(() => {
    if (statusFilter === "Wszystkie") {
      return baseData ?? [];
    }
    return (baseData ?? []).filter(
      (order: Order) => fulfillmentLabel(order.fulfillment_status) === statusFilter
    );
  }, [baseData, statusFilter]);

  async function onRefresh() {
    await queryClient.invalidateQueries({ queryKey: ["orders"] });
  }

  function renderItem({ item }: { item: Order }) {
    return (
      <OrderRow
        order={item}
        onPress={() => navigation.navigate("OrderDetail", { externalId: item.external_id })}
      />
    );
  }

  return (
    <View style={styles.screen}>
      <TabHeading
        title="Zamówienia"
        count={data.length > 0 ? `${data.length} na liście` : undefined}
      />

      <View style={styles.searchWrap}>
        <SearchBar value={query} onChangeText={setQuery} placeholder="Numer, kupujący, produkt…" />
      </View>

      <View style={styles.filterRow}>
        <FlatList
          horizontal
          showsHorizontalScrollIndicator={false}
          data={[...STATUS_FILTERS]}
          keyExtractor={(item) => item}
          renderItem={({ item }) => (
            <FilterChip
              label={counts[item] > 0 || item === "Wszystkie" ? `${item} · ${counts[item]}` : item}
              active={statusFilter === item}
              onPress={() => setStatusFilter(item)}
            />
          )}
          ItemSeparatorComponent={() => <View style={{ width: spacing.sm }} />}
        />
      </View>

      {isPending || isBusy ? (
        <View style={styles.listPadding}>
          <Skeleton height={88} radius={radii.lg} style={{ marginBottom: spacing.sm }} />
          <Skeleton height={88} radius={radii.lg} style={{ marginBottom: spacing.sm }} />
          <Skeleton height={88} radius={radii.lg} />
        </View>
      ) : isError ? (
        <ErrorState onRetry={() => (isSearching ? searchQuery.refetch() : ordersQuery.refetch())} />
      ) : (
        <FlatList
          data={data}
          keyExtractor={(item) => item.external_id}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={ordersQuery.isRefetching}
              onRefresh={onRefresh}
              tintColor={colors.primary}
            />
          }
          ListFooterComponent={
            data.length > 0 ? (
              <ListEndNote text="To wszystkie zamówienia pobrane z Pi. Szczegóły i pakowanie znajdziesz na desktopie." />
            ) : null
          }
          ListEmptyComponent={
            <EmptyState
              mascotPose={!isSearching && statusFilter === "Wszystkie" ? "orders" : undefined}
              icon={
                isSearching || statusFilter !== "Wszystkie" ? (
                  <ReceiptIcon size={24} color={colors.textSecondary} />
                ) : undefined
              }
              title={
                isSearching
                  ? "Nic tu nie ma"
                  : statusFilter !== "Wszystkie"
                    ? `Brak zamówień: ${statusFilter.toLowerCase()}`
                    : "Czekamy na pierwsze zamówienie"
              }
              description={
                isSearching
                  ? "Spróbuj innego numeru, loginu kupującego albo nazwy produktu."
                  : statusFilter !== "Wszystkie"
                    ? "Zmień filtr statusu, żeby zobaczyć pozostałe zamówienia."
                    : "Uruchom synchronizację, żeby pobrać zamówienia z Allegro."
              }
              actionLabel={
                !isSearching && statusFilter === "Wszystkie" ? "Synchronizuj teraz" : undefined
              }
              onAction={!isSearching && statusFilter === "Wszystkie" ? sync : undefined}
            />
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  searchWrap: {
    paddingHorizontal: spacing.xl,
  },
  filterRow: {
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
  },
  listPadding: {
    paddingHorizontal: spacing.xl,
  },
  listContent: {
    paddingHorizontal: spacing.xl,
    paddingBottom: 96,
  },
});
