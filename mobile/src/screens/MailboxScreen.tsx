/**
 * Skrzynka — podgląd maili od Allegro/OLX wykrytych przez skrzynkę (IMAP).
 * Tylko do odczytu - pełną treść i odpowiedzi obsługuje się w Gmailu
 * (link "Otwórz w Gmail" na ekranie podglądu wiadomości).
 */
import * as React from "react";
import { FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useQueryClient } from "@tanstack/react-query";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { useMailMessages } from "@/api/hooks";
import { MailRow } from "@/components/MailRow";
import { FilterChip } from "@/components/FilterChip";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Skeleton } from "@/components/Skeleton";
import type { MailMessage, MailSource } from "@/api/types";
import type { RootStackParamList } from "@/navigation/types";

const SOURCE_FILTERS: { key: MailSource | "all"; label: string }[] = [
  { key: "all", label: "Wszystkie" },
  { key: "allegro", label: "Allegro" },
  { key: "olx", label: "OLX" },
];

export function MailboxScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const queryClient = useQueryClient();
  const [source, setSource] = React.useState<MailSource | "all">("all");
  const mail = useMailMessages(source === "all" ? undefined : source);

  async function onRefresh() {
    await queryClient.invalidateQueries({ queryKey: ["mail-messages"] });
  }

  function renderItem({ item }: { item: MailMessage }) {
    return (
      <MailRow
        message={item}
        onPress={() => navigation.navigate("MailDetail", { messageId: item.message_id })}
      />
    );
  }

  return (
    <View style={styles.screen}>
      <View style={styles.header}>
        <Text style={styles.title}>Skrzynka</Text>
      </View>

      <View style={styles.filterRow}>
        <FlatList
          horizontal
          showsHorizontalScrollIndicator={false}
          data={SOURCE_FILTERS}
          keyExtractor={(item) => item.key}
          renderItem={({ item }) => (
            <FilterChip
              label={item.label}
              active={source === item.key}
              onPress={() => setSource(item.key)}
            />
          )}
          ItemSeparatorComponent={() => <View style={{ width: spacing.sm }} />}
        />
      </View>

      {mail.isPending ? (
        <View style={styles.listPadding}>
          <Skeleton height={84} radius={radii.lg} style={{ marginBottom: spacing.sm }} />
          <Skeleton height={84} radius={radii.lg} />
        </View>
      ) : mail.isError ? (
        <ErrorState onRetry={() => mail.refetch()} />
      ) : (
        <FlatList
          data={mail.data ?? []}
          keyExtractor={(item) => item.message_id}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={mail.isRefetching}
              onRefresh={onRefresh}
              tintColor={colors.primary}
            />
          }
          ListEmptyComponent={
            <EmptyState
              mascotPose="happy"
              title="Brak maili do pokazania"
              description="Nowe wiadomości od Allegro i OLX pojawią się tutaj automatycznie."
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
  filterRow: {
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
  },
  listPadding: {
    paddingHorizontal: spacing.xl,
  },
  listContent: {
    paddingHorizontal: spacing.xl,
    paddingBottom: 110,
  },
});
