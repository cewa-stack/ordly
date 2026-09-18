/**
 * Magazyn — lista tego, co jest wystawione na marketplace'ach: miniatura,
 * tytuł, kanał i cena. Telefon jest tu POGLĄDEM: pokazuje asortyment
 * i pozwala dociągnąć nowe oferty, a ręczne liczenie sztuk zostaje na
 * desktopie, gdzie jest klawiatura i czas.
 *
 * Katalog nie odświeża się sam. Nowa oferta powstaje wtedy, gdy człowiek
 * ją wystawi, więc odpytywanie API marketplace w tle tylko zjadałoby
 * limit zapytań - stąd jawny przycisk „Synchronizuj”.
 */
import * as React from "react";
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { useQueryClient } from "@tanstack/react-query";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { useOffers, useSyncCatalog } from "@/api/hooks";
import { ApiError } from "@/api/client";
import { OfferRow } from "@/components/OfferRow";
import { SearchBar } from "@/components/SearchBar";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { ListEndNote } from "@/components/ListEndNote";
import { Skeleton } from "@/components/Skeleton";
import { BoxIcon, SyncIcon } from "@/icons";
import { formatDate, plural } from "@/utils/format";
import type { MarketplaceOffer } from "@/api/types";

export function StockScreen() {
  const queryClient = useQueryClient();
  const offers = useOffers();
  const sync = useSyncCatalog();

  const [query, setQuery] = React.useState("");
  const [syncNote, setSyncNote] = React.useState<string | null>(null);
  const [syncError, setSyncError] = React.useState<string | null>(null);

  const all: MarketplaceOffer[] = offers.data ?? [];

  const filtered = React.useMemo(() => {
    const items: MarketplaceOffer[] = offers.data ?? [];
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (offer) =>
        offer.name.toLowerCase().includes(q) ||
        (offer.signature ?? "").toLowerCase().includes(q)
    );
  }, [offers.data, query]);

  async function handleSync() {
    setSyncError(null);
    setSyncNote(null);
    try {
      const result = await sync.mutateAsync();
      // Same liczby, nie „gotowe”: po synchronizacji człowiek chce
      // wiedzieć, czy to, co przed chwilą wystawił, faktycznie doszło.
      const parts = [`${result.fetched} ${plural(result.fetched, "oferta", "oferty", "ofert")}`];
      if (result.added > 0) parts.push(`+${result.added} nowych`);
      if (result.removed > 0) parts.push(`−${result.removed} zniknęło`);
      setSyncNote(parts.join(" · "));
    } catch (error) {
      setSyncError(
        error instanceof ApiError ? error.message : "Nie udało się pobrać katalogu"
      );
    }
  }

  // Znaczniki z API są w ISO ze strefą „Z”, więc najświeższy jest
  // największy leksykograficznie - nie ma po co parsować całej listy.
  const lastSynced = all.reduce<string | null>(
    (newest, offer) =>
      offer.synced_at !== null && (newest === null || offer.synced_at > newest)
        ? offer.synced_at
        : newest,
    null
  );

  // Wszystko nad listą jedzie razem z nią przy przewijaniu - na telefonie
  // przyklejony nagłówek zabierał tyle miejsca, że zostawało na dwie
  // karty. To ELEMENT, nie funkcja komponentu: inline'owa funkcja
  // tworzyłaby przy każdym wpisanym znaku nowy typ komponentu, więc pole
  // wyszukiwarki montowałoby się od nowa i gubiło fokus po pierwszej literze.
  const listHeader = (
    <View>
      <View style={styles.syncCard}>
        <View style={styles.syncInfo}>
          <Text style={styles.syncCount}>
            {all.length}{" "}
            {plural(all.length, "oferta", "oferty", "ofert")}
          </Text>
          <Text style={styles.syncMeta} numberOfLines={1}>
            {syncError ?? syncNote ?? (lastSynced ? `Pobrano ${formatDate(lastSynced)}` : "Katalog jeszcze niepobrany")}
          </Text>
        </View>
        <Pressable
          onPress={handleSync}
          disabled={sync.isPending}
          style={({ pressed }) => [
            styles.syncButton,
            (pressed || sync.isPending) && styles.syncButtonPressed,
          ]}
          accessibilityLabel="Pobierz katalog z marketplace"
        >
          <SyncIcon size={16} color={colors.onPrimary} />
          <Text style={styles.syncButtonLabel}>
            {sync.isPending ? "Pobieram…" : "Synchronizuj"}
          </Text>
        </Pressable>
      </View>

      <View style={styles.searchWrap}>
        <SearchBar
          value={query}
          onChangeText={setQuery}
          placeholder="Szukaj po nazwie lub sygnaturze…"
        />
      </View>
    </View>
  );

  return (
    <View style={styles.screen}>
      <View style={styles.header}>
        <Text style={styles.title}>Magazyn</Text>
      </View>

      {offers.isPending ? (
        <View style={styles.listPadding}>
          {listHeader}
          <Skeleton height={80} radius={radii.lg} style={{ marginBottom: spacing.sm }} />
          <Skeleton height={80} radius={radii.lg} />
        </View>
      ) : offers.isError ? (
        <View style={styles.listPadding}>
          {listHeader}
          <ErrorState onRetry={() => offers.refetch()} />
        </View>
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(offer) => `${offer.marketplace}:${offer.external_id}`}
          renderItem={({ item }) => <OfferRow offer={item} />}
          contentContainerStyle={styles.listContent}
          ListHeaderComponent={listHeader}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
          refreshControl={
            <RefreshControl
              refreshing={offers.isRefetching}
              onRefresh={() => queryClient.invalidateQueries({ queryKey: ["offers"] })}
              tintColor={colors.primary}
            />
          }
          ListFooterComponent={
            filtered.length > 0 ? (
              <ListEndNote text="To cały asortyment. Ilość sztuk na półce wpisujesz na desktopie." />
            ) : null
          }
          ListEmptyComponent={
            <EmptyState
              icon={<BoxIcon size={24} color={colors.textSecondary} />}
              title={query.trim() ? "Nie znaleziono oferty" : "Katalog jest pusty"}
              description={
                query.trim()
                  ? "Zmień frazę albo pobierz katalog na nowo."
                  : "Naciśnij „Synchronizuj”, żeby pobrać swoje oferty z marketplace."
              }
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
  header: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.lg,
  },
  title: {
    ...typography.title1,
    color: colors.text,
  },
  syncCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    marginTop: spacing.md,
  },
  syncInfo: {
    flex: 1,
    minWidth: 0,
  },
  syncCount: {
    ...typography.statValue,
    color: colors.text,
  },
  syncMeta: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  syncButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    height: 38,
    paddingHorizontal: spacing.lg,
    borderRadius: radii.full,
    backgroundColor: colors.primary,
  },
  syncButtonPressed: {
    opacity: 0.85,
  },
  syncButtonLabel: {
    ...typography.calloutSemibold,
    color: colors.onPrimary,
  },
  searchWrap: {
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
