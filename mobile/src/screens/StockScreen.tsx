/**
 * Magazyn — §7 specyfikacji: pasek mini-KPI (Produkty · Poniżej minimum ·
 * Wartość), wyszukiwarka, chipy filtrów, karty produktów z paskiem zapasu.
 * Dodawanie produktu przez bottom sheet (grabber, radius 24) z opcjonalnym
 * progiem alertu (min_stock).
 */
import * as React from "react";
import {
  FlatList,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useQueryClient } from "@tanstack/react-query";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import {
  useCreateStockItem,
  useStock,
  useStockReport,
  useUnmappedOffers,
} from "@/api/hooks";
import { ApiError } from "@/api/client";
import { StockRow } from "@/components/StockRow";
import { FilterChip } from "@/components/FilterChip";
import { SearchBar } from "@/components/SearchBar";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { TabHeading } from "@/components/TabHeading";
import { ListEndNote } from "@/components/ListEndNote";
import { PrimaryButton } from "@/components/PrimaryButton";
import { Skeleton } from "@/components/Skeleton";
import { BoxIcon, PlusIcon } from "@/icons";
import { formatMoney } from "@/utils/format";
import type { StockItem, UnmappedOffer } from "@/api/types";
import type { RootStackParamList } from "@/navigation/types";

type Filter = "all" | "low" | "no-sales";

export function StockScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const queryClient = useQueryClient();
  const stock = useStock();
  const report = useStockReport();
  const unmapped = useUnmappedOffers();
  const createItem = useCreateStockItem();

  const [query, setQuery] = React.useState("");
  const [filter, setFilter] = React.useState<Filter>("all");
  const [modalOpen, setModalOpen] = React.useState(false);
  const [newSku, setNewSku] = React.useState("");
  const [newName, setNewName] = React.useState("");
  const [newMinStock, setNewMinStock] = React.useState("");
  const [createError, setCreateError] = React.useState<string | null>(null);

  const noSalesSkus = React.useMemo(
    () => new Set((report.data?.items_without_sales ?? []).map((i: StockItem) => i.sku)),
    [report.data]
  );

  const filtered = React.useMemo(() => {
    let items: StockItem[] = stock.data ?? [];
    if (filter === "low") {
      items = items.filter((i: StockItem) => i.status !== "ok");
    } else if (filter === "no-sales") {
      items = items.filter((i: StockItem) => noSalesSkus.has(i.sku));
    }
    const q = query.trim().toLowerCase();
    if (q) {
      items = items.filter(
        (i: StockItem) => i.name.toLowerCase().includes(q) || i.sku.toLowerCase().includes(q)
      );
    }
    return items;
  }, [stock.data, filter, query, noSalesSkus]);

  async function onRefresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["stock"] }),
      queryClient.invalidateQueries({ queryKey: ["stock-report"] }),
    ]);
  }

  function closeModal() {
    setModalOpen(false);
    setCreateError(null);
  }

  async function handleCreate() {
    setCreateError(null);
    if (!newSku.trim() || !newName.trim()) {
      setCreateError("Podaj SKU i nazwę produktu");
      return;
    }
    const minStock = newMinStock.trim() ? Number(newMinStock) : undefined;
    if (minStock !== undefined && (!Number.isFinite(minStock) || minStock < 0)) {
      setCreateError("Próg alertu musi być liczbą nieujemną");
      return;
    }
    try {
      await createItem.mutateAsync({
        sku: newSku.trim(),
        name: newName.trim(),
        ...(minStock !== undefined ? { min_stock: minStock } : {}),
      });
      setModalOpen(false);
      setNewSku("");
      setNewName("");
      setNewMinStock("");
    } catch (error) {
      setCreateError(error instanceof ApiError ? error.message : "Nie udało się dodać produktu");
    }
  }

  function renderItem({ item }: { item: StockItem }) {
    return (
      <StockRow item={item} onPress={() => navigation.navigate("StockItem", { sku: item.sku })} />
    );
  }

  const lowCount = report.data?.low_stock_items.length ?? 0;
  const unmappedCount = unmapped.data?.length ?? 0;
  const unmappedNames = (unmapped.data ?? [])
    .slice(0, 2)
    .map((offer: UnmappedOffer) => offer.name)
    .join(", ");

  return (
    <View style={styles.screen}>
      <View style={styles.header}>
        <Text style={styles.title}>Magazyn</Text>
        <Pressable
          onPress={() => setModalOpen(true)}
          style={({ pressed }) => [styles.addButton, pressed && styles.addButtonPressed]}
          hitSlop={8}
        >
          <PlusIcon size={18} color={colors.onPrimary} />
        </Pressable>
      </View>

      {report.data ? (
        <View style={styles.summary}>
          <View style={styles.summaryCell}>
            <Text style={styles.summaryValue}>{report.data.total_items}</Text>
            <Text style={styles.summaryLabel}>Produkty</Text>
          </View>
          <View style={styles.summaryDivider} />
          <View style={styles.summaryCell}>
            <Text style={[styles.summaryValue, lowCount > 0 && { color: colors.warning }]}>
              {lowCount}
            </Text>
            <Text style={styles.summaryLabel}>Poniżej minimum</Text>
          </View>
          <View style={styles.summaryDivider} />
          <View style={styles.summaryCell}>
            <Text style={styles.summaryValue} numberOfLines={1} adjustsFontSizeToFit>
              {formatMoney(report.data.total_stock_value)}
            </Text>
            <Text style={styles.summaryLabel}>Wartość</Text>
          </View>
        </View>
      ) : null}

      {unmappedCount > 0 ? (
        <View style={styles.warningCard}>
          <Text style={styles.warningTitle}>
            {unmappedCount === 1
              ? "1 oferta sprzedaje się poza magazynem"
              : `${unmappedCount} oferty sprzedają się poza magazynem`}
          </Text>
          <Text style={styles.warningBody}>
            {unmappedNames}
            {unmappedNames ? " — " : ""}
            sprzedaż tych ofert nie zdejmuje nic ze stanów, bo nie mają przypisanych
            składników. Powiązania ustawisz na desktopie: Magazyn → Powiązania ofert.
          </Text>
        </View>
      ) : null}

      <View style={styles.searchWrap}>
        <SearchBar value={query} onChangeText={setQuery} placeholder="Szukaj po SKU lub nazwie…" />
      </View>

      <View style={styles.filterRow}>
        <FlatList
          horizontal
          showsHorizontalScrollIndicator={false}
          data={
            [
              { key: "all" as Filter, label: `Wszystkie · ${stock.data?.length ?? 0}` },
              { key: "low" as Filter, label: `Niski stan · ${lowCount}` },
              { key: "no-sales" as Filter, label: "Bez sprzedaży 30 dni" },
            ] satisfies { key: Filter; label: string }[]
          }
          keyExtractor={(item) => item.key}
          renderItem={({ item }) => (
            <FilterChip
              label={item.label}
              active={filter === item.key}
              onPress={() => setFilter(item.key)}
            />
          )}
          ItemSeparatorComponent={() => <View style={{ width: spacing.sm }} />}
        />
      </View>

      {stock.isPending ? (
        <View style={styles.listPadding}>
          <Skeleton height={76} radius={radii.lg} style={{ marginBottom: spacing.sm }} />
          <Skeleton height={76} radius={radii.lg} />
        </View>
      ) : stock.isError ? (
        <ErrorState onRetry={() => stock.refetch()} />
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(item) => item.sku}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={stock.isRefetching}
              onRefresh={onRefresh}
              tintColor={colors.primary}
            />
          }
          ListFooterComponent={
            (stock.data ?? []).length > 0 ? (
              <ListEndNote text="To cały magazyn. Korektę stanu i progi ustawiasz na desktopie." />
            ) : null
          }
          ListEmptyComponent={
            <EmptyState
              icon={<BoxIcon size={24} color={colors.textSecondary} />}
              title={
                query.trim() ? "Nie znaleziono produktu" : "Brak produktów spełniających filtr"
              }
              description="Zmień filtr albo dodaj nowy produkt."
              actionLabel="Dodaj produkt"
              onAction={() => setModalOpen(true)}
            />
          }
        />
      )}

      <Modal visible={modalOpen} animationType="slide" transparent onRequestClose={closeModal}>
        <KeyboardAvoidingView
          style={styles.modalBackdrop}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
        >
          <Pressable style={styles.modalScrim} onPress={closeModal} />
          <View style={styles.modalCard}>
            <View style={styles.grabber} />
            <Text style={styles.modalTitle}>Nowy produkt</Text>
            <TextInput
              value={newSku}
              onChangeText={setNewSku}
              placeholder="SKU (np. PET60)"
              placeholderTextColor={colors.textDim}
              autoCapitalize="characters"
              style={styles.modalInput}
            />
            <TextInput
              value={newName}
              onChangeText={setNewName}
              placeholder="Nazwa (np. Butelka PET 60ml)"
              placeholderTextColor={colors.textDim}
              style={styles.modalInput}
            />
            <TextInput
              value={newMinStock}
              onChangeText={setNewMinStock}
              placeholder="Próg alertu w szt. (opcjonalnie)"
              placeholderTextColor={colors.textDim}
              keyboardType="number-pad"
              style={styles.modalInput}
            />
            {createError ? <Text style={styles.modalError}>{createError}</Text> : null}
            <View style={styles.modalActions}>
              <Pressable
                onPress={closeModal}
                style={({ pressed }) => [
                  styles.modalButton,
                  styles.modalButtonGhost,
                  pressed && { opacity: 0.8 },
                ]}
              >
                <Text style={styles.modalButtonGhostLabel}>Anuluj</Text>
              </Pressable>
              <PrimaryButton
                label="Dodaj"
                onPress={handleCreate}
                loading={createItem.isPending}
                style={styles.modalPrimaryButton}
              />
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.lg,
  },
  title: {
    ...typography.title1,
    color: colors.text,
  },
  addButton: {
    width: 40,
    height: 40,
    borderRadius: radii.full,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  addButtonPressed: {
    opacity: 0.85,
  },
  summary: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    marginHorizontal: spacing.xl,
    marginTop: spacing.md,
  },
  summaryCell: {
    flex: 1,
  },
  summaryValue: {
    ...typography.statValue,
    fontSize: 18,
    color: colors.text,
  },
  summaryLabel: {
    ...typography.caption,
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 2,
  },
  summaryDivider: {
    width: 1,
    backgroundColor: colors.border,
    marginHorizontal: spacing.md,
  },
  warningCard: {
    backgroundColor: colors.warningTint,
    borderWidth: 1,
    borderColor: colors.warning,
    borderRadius: radii.lg,
    padding: spacing.lg,
    marginHorizontal: spacing.xl,
    marginTop: spacing.md,
    gap: spacing.xs,
  },
  warningTitle: {
    ...typography.body,
    fontWeight: "600",
    color: colors.warning,
  },
  warningBody: {
    ...typography.caption,
    color: colors.textSecondary,
    lineHeight: 17,
  },
  searchWrap: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
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
  modalBackdrop: {
    flex: 1,
    justifyContent: "flex-end",
  },
  modalScrim: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.55)",
  },
  modalCard: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radii.sheet,
    borderTopRightRadius: radii.sheet,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.xl,
    paddingBottom: spacing.xxl,
    gap: spacing.sm,
  },
  grabber: {
    width: 36,
    height: 4,
    borderRadius: radii.full,
    backgroundColor: colors.border,
    alignSelf: "center",
    marginBottom: spacing.sm,
  },
  modalTitle: {
    ...typography.title2,
    fontSize: 19,
    lineHeight: 25,
    color: colors.text,
    marginBottom: spacing.xs,
  },
  modalInput: {
    height: 52,
    backgroundColor: colors.surfaceRaised,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    paddingHorizontal: spacing.lg,
    color: colors.text,
    fontSize: 15,
  },
  modalError: {
    ...typography.caption,
    color: colors.danger,
  },
  modalActions: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  modalButton: {
    flex: 1,
    height: 48,
    backgroundColor: colors.primary,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
  },
  modalButtonGhost: {
    backgroundColor: colors.surfaceRaised,
    borderWidth: 1,
    borderColor: colors.border,
  },
  modalButtonGhostLabel: {
    fontSize: 15,
    fontWeight: "600",
    color: colors.textSecondary,
  },
  modalPrimaryButton: {
    flex: 1,
    height: 48,
  },
});
