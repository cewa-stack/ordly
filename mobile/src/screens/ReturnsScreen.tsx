/**
 * Zwroty i anulowane — podgląd tylko do odczytu (bez akcji). Zwroty
 * synchronizują się razem z zamówieniami (Zamówienia → Synchronizuj) -
 * tu tylko odświeżamy listę pociągniętą z lokalnej bazy.
 */
import * as React from "react";
import { FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import { useQueryClient } from "@tanstack/react-query";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { useReturns } from "@/api/hooks";
import { ReturnRow } from "@/components/ReturnRow";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Skeleton } from "@/components/Skeleton";
import type { ReturnItem } from "@/api/types";

export function ReturnsScreen() {
  const returns = useReturns();
  const queryClient = useQueryClient();

  async function onRefresh() {
    await queryClient.invalidateQueries({ queryKey: ["returns"] });
  }

  function renderItem({ item }: { item: ReturnItem }) {
    return <ReturnRow item={item} />;
  }

  return (
    <View style={styles.screen}>
      <View style={styles.header}>
        <Text style={styles.title}>Zwroty i anulowane</Text>
      </View>
      <Text style={styles.note}>
        Zwroty synchronizują się razem z zamówieniami — użyj „Synchronizuj" na ekranie Zamówień,
        żeby sprawdzić nowe.
      </Text>

      {returns.isPending ? (
        <View style={styles.listPadding}>
          <Skeleton height={100} radius={radii.lg} style={{ marginBottom: spacing.sm }} />
          <Skeleton height={100} radius={radii.lg} />
        </View>
      ) : returns.isError ? (
        <ErrorState onRetry={() => returns.refetch()} />
      ) : (
        <FlatList
          data={returns.data ?? []}
          keyExtractor={(item) => item.external_id}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={returns.isRefetching}
              onRefresh={onRefresh}
              tintColor={colors.primary}
            />
          }
          ListEmptyComponent={
            <EmptyState
              mascotPose="happy"
              title="Zero zwrotów i anulowań"
              description="Wszystkie zamówienia idą gładko — nic tu dziś nie ma."
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
  note: {
    ...typography.footnote,
    color: colors.textSecondary,
    paddingHorizontal: spacing.xl,
    marginTop: spacing.xs,
    marginBottom: spacing.md,
  },
  listPadding: {
    paddingHorizontal: spacing.xl,
  },
  listContent: {
    paddingHorizontal: spacing.xl,
    paddingBottom: 110,
  },
});
