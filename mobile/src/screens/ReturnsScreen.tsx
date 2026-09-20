/**
 * Zwroty i anulowane — podgląd tylko do odczytu (bez akcji). Zwroty
 * synchronizują się razem z zamówieniami (Zamówienia → Synchronizuj) -
 * tu tylko odświeżamy listę pociągniętą z lokalnej bazy.
 */
import * as React from "react";
import { FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import { useQueryClient } from "@tanstack/react-query";

import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { radii, spacing, typography } from "@/theme/typography";
import { useReturns } from "@/api/hooks";
import { ReturnRow } from "@/components/ReturnRow";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { TabHeading } from "@/components/TabHeading";
import { ListEndNote } from "@/components/ListEndNote";
import { Skeleton } from "@/components/Skeleton";
import type { ReturnItem } from "@/api/types";

export function ReturnsScreen() {
  const styles = useThemedStyles(createStyles);
  const { c } = useTheme();
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
      <TabHeading title="Zwroty" />

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
              tintColor={c.acc}
            />
          }
          ListFooterComponent={
            (returns.data ?? []).length > 0 ? (
              <ListEndNote text="To ostatnie zwroty pobrane z Allegro. Ordi da znać, gdy pojawi się nowy." />
            ) : null
          }
          ListEmptyComponent={
            <EmptyState
              mascotPose="sleep"
              title="Zero zwrotów"
              description="Wszystkie zamówienia idą gładko — żaden kupujący niczego nie zwraca."
            />
          }
        />
      )}
    </View>
  );
}

const createStyles = (c: Palette) =>
  StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: c.bg,
  },
  header: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.lg,
  },
  title: {
    ...typography.title1,
    color: c.tx,
  },
  note: {
    ...typography.footnote,
    color: c.tx2,
    paddingHorizontal: spacing.xl,
    marginTop: spacing.xs,
    marginBottom: spacing.md,
  },
  listPadding: {
    paddingHorizontal: spacing.xl,
  },
  listContent: {
    paddingHorizontal: spacing.xl,
    paddingBottom: 96,
  },
});
