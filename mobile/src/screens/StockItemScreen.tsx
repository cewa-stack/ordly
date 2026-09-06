/**
 * Szczegóły produktu — §7 specyfikacji: karta hero ze stanem i paskiem
 * zapasu, korekta stanu z wymaganym kontekstem (powód: Dostawa /
 * Inwentaryzacja / Uszkodzenie / Inne — audytowalność klasy enterprise),
 * edytowalny próg alertu, historia ruchów magazynowych.
 */
import * as React from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useRoute, type RouteProp } from "@react-navigation/native";

import { colors, stockStatusColor } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { useAdjustStock, useStockHistory, useStockItem } from "@/api/hooks";
import { ApiError } from "@/api/client";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";
import { PrimaryButton } from "@/components/PrimaryButton";
import { Skeleton } from "@/components/Skeleton";
import { FilterChip } from "@/components/FilterChip";
import { formatMoney } from "@/utils/format";
import type { StockAdjustOp, StockItem, StockMovement } from "@/api/types";
import type { RootStackParamList } from "@/navigation/types";

const ADJUST_REASONS = ["Dostawa", "Inwentaryzacja", "Uszkodzenie", "Inne"] as const;
type AdjustReason = (typeof ADJUST_REASONS)[number];

function relativeDate(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function StockItemScreen() {
  const route = useRoute<RouteProp<RootStackParamList, "StockItem">>();
  const { sku } = route.params;
  const item = useStockItem(sku);
  const history = useStockHistory(sku);
  const adjust = useAdjustStock();

  const [amount, setAmount] = React.useState("1");
  const [reason, setReason] = React.useState<AdjustReason>("Dostawa");
  const [minInput, setMinInput] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (item.data && minInput === null) {
      setMinInput(String(item.data.min_stock));
    }
  }, [item.data, minInput]);

  async function runAdjust(op: StockAdjustOp, quantity: number) {
    setActionError(null);
    try {
      await adjust.mutateAsync({ sku, op, quantity, reason: op === "min" ? undefined : reason });
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : "Nie udało się zaktualizować stanu");
    }
  }

  async function saveMinStock() {
    const parsed = Number(minInput);
    if (!Number.isFinite(parsed) || parsed < 0) {
      setActionError("Podaj poprawną wartość minimalnego stanu");
      return;
    }
    await runAdjust("min", parsed);
  }

  if (item.isPending) {
    return (
      <View style={styles.screen}>
        <Skeleton height={160} radius={radii.xl} style={{ margin: spacing.xl }} />
      </View>
    );
  }

  if (item.isError || !item.data) {
    return (
      <View style={styles.screen}>
        <ErrorState message="Nie znaleziono produktu" onRetry={() => item.refetch()} />
      </View>
    );
  }

  const data: StockItem = item.data;
  const ratio = data.min_stock > 0 ? data.stock / (data.min_stock * 2) : data.stock > 0 ? 1 : 0;
  const barWidth = `${Math.max(4, Math.min(100, Math.round(ratio * 100)))}%` as const;
  const barColor = stockStatusColor[data.status];
  const parsedAmount = Math.max(1, Math.round(Number(amount) || 1));

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <View style={styles.heroCard}>
        <Text style={styles.name}>{data.name}</Text>
        <Text style={styles.sku}>{data.sku}</Text>
        <View style={styles.stockRow}>
          <Text style={styles.stockValue}>
            {data.stock} <Text style={styles.stockUnit}>szt.</Text>
          </Text>
          <Text style={styles.stockMin}>próg alertu: {data.min_stock}</Text>
        </View>
        <View style={styles.bar}>
          <View style={[styles.barFill, { width: barWidth, backgroundColor: barColor }]} />
        </View>
        {/* Zero znaczy "brak ceny zakupu" - wiersz z 0,00 zl nic by nie wnosil.
            Warunek jest jawny, bo kwoty przychodza teraz jako liczby: samo
            `data.stock_value ?` chowaloby tez uczciwe zero. */}
        {Number(data.stock_value) > 0 ? (
          <Text style={styles.value}>Wartość pozycji: {formatMoney(data.stock_value)}</Text>
        ) : null}
      </View>

      <Text style={styles.sectionTitle}>Korekta stanu</Text>
      <View style={styles.card}>
        <Text style={styles.fieldLabel}>Powód korekty</Text>
        <View style={styles.reasonRow}>
          {ADJUST_REASONS.map((r) => (
            <FilterChip key={r} label={r} active={reason === r} onPress={() => setReason(r)} />
          ))}
        </View>

        <View style={styles.amountRow}>
          <TextInput
            value={amount}
            onChangeText={setAmount}
            keyboardType="number-pad"
            style={styles.amountInput}
          />
          <View style={styles.actionButtons}>
            <Pressable
              style={({ pressed }) => [
                styles.actionButton,
                styles.actionButtonGhost,
                pressed && { opacity: 0.8 },
              ]}
              onPress={() => runAdjust("remove", parsedAmount)}
              disabled={adjust.isPending}
            >
              <Text style={styles.actionButtonGhostLabel}>− Odejmij</Text>
            </Pressable>
            <PrimaryButton
              label="+ Dodaj"
              onPress={() => runAdjust("add", parsedAmount)}
              disabled={adjust.isPending}
              style={styles.addButtonFlex}
            />
          </View>
        </View>
        <Pressable
          style={({ pressed }) => [
            styles.actionButton,
            styles.actionButtonGhost,
            { marginTop: spacing.sm },
            pressed && { opacity: 0.8 },
          ]}
          onPress={() => runAdjust("set", parsedAmount)}
          disabled={adjust.isPending}
        >
          <Text style={styles.actionButtonGhostLabel}>Ustaw stan na {parsedAmount}</Text>
        </Pressable>

        <View style={styles.minRow}>
          <Text style={styles.minLabel}>Próg alertu (minimum)</Text>
          <TextInput
            value={minInput ?? ""}
            onChangeText={setMinInput}
            keyboardType="number-pad"
            style={styles.minInput}
          />
          <Pressable onPress={saveMinStock} hitSlop={8} disabled={adjust.isPending}>
            <Text style={styles.minSave}>Zapisz</Text>
          </Pressable>
        </View>

        {adjust.isPending ? (
          <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.sm }} />
        ) : null}
        {actionError ? <Text style={styles.error}>{actionError}</Text> : null}
      </View>

      <Text style={styles.sectionTitle}>Historia ruchów</Text>
      <View style={styles.card}>
        {history.isPending ? (
          <Skeleton height={40} />
        ) : history.isError ? (
          <ErrorState onRetry={() => history.refetch()} />
        ) : (history.data ?? []).length === 0 ? (
          <EmptyState title="Brak historii zmian" />
        ) : (
          (history.data ?? []).map((movement: StockMovement, index: number) => (
            <View
              key={`${movement.occurred_at}-${index}`}
              style={[styles.historyRow, index === 0 && styles.historyRowFirst]}
            >
              <View style={styles.historyTop}>
                <Text style={styles.historyReason} numberOfLines={1}>
                  {movement.reason}
                </Text>
                <Text
                  style={[
                    styles.historyChange,
                    { color: movement.change >= 0 ? colors.success : colors.textSecondary },
                  ]}
                >
                  {movement.change >= 0 ? "+" : ""}
                  {movement.change}
                </Text>
              </View>
              <Text style={styles.historyMeta}>
                {relativeDate(movement.occurred_at)} · stan po zmianie: {movement.stock_after}
              </Text>
            </View>
          ))
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
  name: {
    ...typography.calloutSemibold,
    fontSize: 17,
    color: colors.text,
  },
  sku: {
    ...typography.mono,
    fontSize: 12,
    color: colors.textDim,
    marginTop: 2,
  },
  stockRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginTop: spacing.lg,
  },
  stockValue: {
    ...typography.display,
    fontSize: 30,
    lineHeight: 36,
    color: colors.text,
  },
  stockUnit: {
    ...typography.footnote,
    color: colors.textSecondary,
  },
  stockMin: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  bar: {
    height: 4,
    borderRadius: radii.full,
    backgroundColor: colors.surfaceRaised,
    marginTop: spacing.md,
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: radii.full,
  },
  value: {
    ...typography.footnote,
    color: colors.textSecondary,
    marginTop: spacing.md,
  },
  sectionTitle: {
    ...typography.sectionTitle,
    color: colors.text,
    marginTop: spacing.xl,
    marginBottom: spacing.md,
  },
  fieldLabel: {
    ...typography.caption,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  reasonRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  amountRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  amountInput: {
    width: 72,
    height: 48,
    backgroundColor: colors.surfaceRaised,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    textAlign: "center",
    color: colors.text,
    fontSize: 16,
    fontWeight: "600",
  },
  actionButtons: {
    flex: 1,
    flexDirection: "row",
    gap: spacing.sm,
  },
  actionButton: {
    flex: 1,
    height: 48,
    backgroundColor: colors.primary,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
  },
  actionButtonGhost: {
    backgroundColor: colors.surfaceRaised,
    borderWidth: 1,
    borderColor: colors.border,
  },
  addButtonFlex: {
    flex: 1,
    height: 48,
  },
  actionButtonGhostLabel: {
    fontSize: 15,
    fontWeight: "600",
    color: colors.text,
  },
  minRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.lg,
    paddingTop: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  minLabel: {
    ...typography.footnote,
    color: colors.textSecondary,
    flex: 1,
  },
  minInput: {
    width: 64,
    height: 40,
    backgroundColor: colors.surfaceRaised,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    textAlign: "center",
    color: colors.text,
    fontSize: 14,
  },
  minSave: {
    ...typography.caption,
    fontSize: 13,
    fontWeight: "600",
    color: colors.primary,
  },
  error: {
    ...typography.caption,
    color: colors.danger,
    marginTop: spacing.sm,
  },
  historyRow: {
    paddingVertical: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  historyRowFirst: {
    borderTopWidth: 0,
    paddingTop: 0,
  },
  historyTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  historyReason: {
    ...typography.footnote,
    fontWeight: "600",
    color: colors.text,
    flexShrink: 1,
  },
  historyChange: {
    ...typography.mono,
    fontSize: 14,
    fontWeight: "700",
  },
  historyMeta: {
    ...typography.caption,
    fontSize: 11.5,
    color: colors.textDim,
    marginTop: 2,
  },
});
