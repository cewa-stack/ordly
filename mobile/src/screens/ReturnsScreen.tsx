/**
 * Zwroty i anulowane - podgląd tylko do odczytu (bez akcji), te same
 * sekcje i podzakładki co na desktopie (pozycja z Notion "Podział zwrotów
 * i anulowanych zamówień na osobne podzakładki oraz statusy obsługi"):
 *
 *   Zwroty | Anulowane zamówienia
 *   Zgłoszony | W trakcie realizacji | Zakończony
 *
 * Status obsługi zwrotów liczy Pi z Allegro (`handling_status`), status
 * anulowanych zamówień ustawia się na desktopie. Telefon nie pokazuje
 * danych kontaktowych - rejestr ich zresztą nie przechowuje (decyzje D7,
 * D8-a). Dane synchronizują się razem z zamówieniami.
 */
import * as React from "react";
import { FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import { useQueryClient } from "@tanstack/react-query";

import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { radii, spacing, typography } from "@/theme/typography";
import { useCustomerCases, useReturns } from "@/api/hooks";
import { ReturnRow } from "@/components/ReturnRow";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FilterChip } from "@/components/FilterChip";
import { TabHeading } from "@/components/TabHeading";
import { ListEndNote } from "@/components/ListEndNote";
import { Skeleton } from "@/components/Skeleton";
import { formatDate } from "@/utils/format";
import type { CaseHandling, CustomerCase, ReturnItem } from "@/api/types";

type Section = "returns" | "cancelled";

const SECTIONS: { key: Section; label: string }[] = [
  { key: "returns", label: "Zwroty" },
  { key: "cancelled", label: "Anulowane zamówienia" },
];

const HANDLING: { key: CaseHandling; label: string }[] = [
  { key: "REPORTED", label: "Zgłoszony" },
  { key: "IN_PROGRESS", label: "W trakcie realizacji" },
  { key: "DONE", label: "Zakończony" },
];

const CLOSED = new Set([
  "FINISHED",
  "FINISHED_APT",
  "REJECTED",
  "COMMISSION_REFUND_CLAIMED",
  "COMMISSION_REFUNDED",
  "CANCELLED",
]);
const IN_PROGRESS = new Set([
  "DISPATCHED",
  "IN_TRANSIT",
  "DELIVERED",
  "WAREHOUSE_DELIVERED",
  "WAREHOUSE_VERIFICATION",
]);

/** `handling_status` z Pi; zapas dla starszego Pi - ta sama reguła. */
function returnHandling(item: ReturnItem): CaseHandling {
  if (item.handling_status) return item.handling_status;
  const open =
    typeof item.requires_action === "boolean" ? item.requires_action : !CLOSED.has(item.status);
  if (!open) return "DONE";
  return IN_PROGRESS.has(item.status) ? "IN_PROGRESS" : "REPORTED";
}

const MISSING = "nieuzupełnione";

function CaseCard({ item }: { item: CustomerCase }) {
  const styles = useThemedStyles(createStyles);
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle} numberOfLines={1}>
        {item.buyer_login ?? `login ${MISSING}`}
      </Text>
      <Text style={styles.cardMeta} numberOfLines={1}>
        {item.order_external_id.slice(0, 8).toUpperCase()} · {item.kind_label}
      </Text>
      <Text style={styles.cardMeta} numberOfLines={2}>
        Złożone {item.order_date ? formatDate(item.order_date) : MISSING} · anulowane{" "}
        {item.cancelled_at ? formatDate(item.cancelled_at) : MISSING}
        {item.refunded_at ? ` · zwrot pieniędzy ${formatDate(item.refunded_at)}` : ""}
      </Text>
      <Text style={styles.cardReason} numberOfLines={1}>
        Powód: {item.reason_label}
      </Text>
    </View>
  );
}

export function ReturnsScreen() {
  const styles = useThemedStyles(createStyles);
  const { c } = useTheme();
  const [section, setSection] = React.useState<Section>("returns");
  const [handling, setHandling] = React.useState<CaseHandling>("REPORTED");
  const returns = useReturns();
  const cases = useCustomerCases();
  const queryClient = useQueryClient();

  const cancelled = React.useMemo(
    (): CustomerCase[] =>
      ((cases.data ?? []) as CustomerCase[]).filter((item) => item.kind !== "REFUND"),
    [cases.data]
  );

  const counts = React.useMemo(() => {
    const result: Record<CaseHandling, number> = { REPORTED: 0, IN_PROGRESS: 0, DONE: 0 };
    if (section === "returns") {
      for (const item of (returns.data ?? []) as ReturnItem[]) result[returnHandling(item)] += 1;
    } else {
      for (const item of cancelled) result[item.handling_status] += 1;
    }
    return result;
  }, [section, returns.data, cancelled]);

  async function onRefresh() {
    await queryClient.invalidateQueries({ queryKey: ["returns"] });
    await queryClient.invalidateQueries({ queryKey: ["customer-cases"] });
  }

  const active = section === "returns" ? returns : cases;
  const isPending = active.isPending;
  const isError = active.isError && !active.data;

  const header = (
    <View style={styles.filters}>
      <View style={styles.row}>
        {SECTIONS.map((option) => (
          <FilterChip
            key={option.key}
            label={option.label}
            active={section === option.key}
            onPress={() => setSection(option.key)}
          />
        ))}
      </View>
      <View style={styles.row}>
        {HANDLING.map((option) => (
          <FilterChip
            key={option.key}
            label={`${option.label} · ${counts[option.key]}`}
            active={handling === option.key}
            onPress={() => setHandling(option.key)}
          />
        ))}
      </View>
    </View>
  );

  const refresh = (
    <RefreshControl refreshing={active.isRefetching} onRefresh={onRefresh} tintColor={c.acc} />
  );

  return (
    <View style={styles.screen}>
      <TabHeading title="Zwroty" />

      {isPending ? (
        <View style={styles.listPadding}>
          <Skeleton height={100} radius={radii.lg} style={{ marginBottom: spacing.sm }} />
          <Skeleton height={100} radius={radii.lg} />
        </View>
      ) : isError ? (
        <ErrorState onRetry={() => active.refetch()} />
      ) : section === "returns" ? (
        <FlatList
          data={((returns.data ?? []) as ReturnItem[]).filter((item) => returnHandling(item) === handling)}
          keyExtractor={(item) => item.external_id}
          renderItem={({ item }) => <ReturnRow item={item} />}
          ListHeaderComponent={header}
          contentContainerStyle={styles.listContent}
          refreshControl={refresh}
          ListFooterComponent={
            (returns.data ?? []).length > 0 ? (
              <ListEndNote text="Status obsługi zwrotu wynika z Allegro. Ordi da znać, gdy pojawi się nowy zwrot." />
            ) : null
          }
          ListEmptyComponent={
            <EmptyState
              mascotPose="sleep"
              mascotProp="box"
              title="Pusto w tej zakładce"
              description="Żaden zwrot nie ma teraz tego statusu."
            />
          }
        />
      ) : (
        <FlatList
          data={cancelled.filter((item) => item.handling_status === handling)}
          keyExtractor={(item) => String(item.id)}
          renderItem={({ item }) => <CaseCard item={item} />}
          ListHeaderComponent={header}
          contentContainerStyle={styles.listContent}
          refreshControl={refresh}
          ListFooterComponent={
            cancelled.length > 0 ? (
              <ListEndNote text="Powód i status obsługi zmieniasz na desktopie." />
            ) : null
          }
          ListEmptyComponent={
            <EmptyState
              mascotPose="sleep"
              mascotProp="box"
              title="Pusto w tej zakładce"
              description="Żadne anulowane zamówienie nie ma teraz tego statusu."
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
    filters: {
      gap: spacing.sm,
      marginBottom: spacing.md,
    },
    row: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: spacing.sm,
    },
    listPadding: {
      paddingHorizontal: spacing.xl,
    },
    listContent: {
      paddingHorizontal: spacing.xl,
      paddingBottom: 96,
    },
    card: {
      borderRadius: radii.lg,
      backgroundColor: c.card,
      borderWidth: 1,
      borderColor: c.line,
      paddingVertical: 13,
      paddingHorizontal: 15,
      marginBottom: 8,
      gap: 3,
    },
    cardTitle: {
      ...typography.headline,
      color: c.tx,
    },
    cardMeta: {
      ...typography.footnote,
      color: c.tx3,
    },
    cardReason: {
      ...typography.footnote,
      color: c.tx2,
    },
  });
