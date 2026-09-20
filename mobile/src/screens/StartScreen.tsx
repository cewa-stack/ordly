/**
 * Start - pierwsza zakładka (sekcja 12 instrukcji "Nokturn").
 *
 *   nagłówek
 *   karta Ordlaka      <- stan systemu, dotknięcie synchronizuje
 *   kafle 2 x 2
 *   "Wymaga uwagi"     <- zamówienia czekające na spakowanie
 *
 * Ten ekran przejmuje też rolę ROZDROŻA: Dyskusje i Zwroty zeszły z
 * paska zakładek, więc prowadzą tu do nich własne kafle. Żadna funkcja
 * nie zniknęła razem z zakładką - to byłby ślepy zaułek.
 *
 * Treść ma wygaszenie u dołu (sekcja 11), żeby ucięta lista nie wyglądała
 * na błąd. W RN nie ma `mask-image`, więc robi to nakładka z gradientem.
 */
import * as React from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { fonts, radii, spacing } from "@/theme/typography";
import { TabHeading } from "@/components/TabHeading";
import { Ordlak, type OrdlakState } from "@/components/Ordlak";
import { OrderRow } from "@/components/OrderRow";
import { useDashboard, useIssues, useOrders, useReturns } from "@/api/hooks";
import { useSync } from "@/store/sync";
import { formatMoney, isPendingFulfillment, parseApiDate } from "@/utils/format";
import type { Issue, Order, ReturnItem } from "@/api/types";
import type { RootStackParamList } from "@/navigation/types";

/**
 * Zwroty, które nie wymagają już niczego od sprzedawcy - te same, które
 * ekran Zwroty pokazuje wygaszone.
 */
const CLOSED_RETURNS = new Set(["COMMISSION_REFUNDED", "CANCELLED", "REJECTED"]);

type Tint = "acc" | "coral" | "violet" | "amber";

function Tile({
  label,
  value,
  unit,
  delta,
  tint,
  onPress,
}: {
  label: string;
  value: string;
  unit?: string;
  delta?: string;
  tint: Tint;
  onPress?: () => void;
}) {
  const styles = useThemedStyles(createStyles);
  const { c } = useTheme();
  const dotColor = { acc: c.acc, coral: c.coral, violet: c.violet, amber: c.amber }[tint];

  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      accessibilityRole={onPress ? "button" : undefined}
      style={({ pressed }) => [styles.tile, pressed && styles.pressed]}
    >
      <View style={styles.tileLabelRow}>
        <View style={[styles.dot, { backgroundColor: dotColor }]} />
        <Text style={styles.tileLabel} numberOfLines={1}>
          {label}
        </Text>
      </View>
      <View style={styles.tileValueRow}>
        <Text style={styles.tileValue} numberOfLines={1}>
          {value}
        </Text>
        {unit ? <Text style={styles.tileUnit}>{unit}</Text> : null}
      </View>
      {delta ? (
        <Text style={styles.tileDelta} numberOfLines={1}>
          {delta}
        </Text>
      ) : null}
    </Pressable>
  );
}

export function StartScreen() {
  const styles = useThemedStyles(createStyles);
  const { c } = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { phase, sync } = useSync();

  const dashboard = useDashboard();
  const ordersQuery = useOrders();
  const issuesQuery = useIssues();
  const returnsQuery = useReturns();

  const orders = (ordersQuery.data ?? []) as Order[];
  const pending = orders.filter(isPendingFulfillment);
  const openIssues = ((issuesQuery.data ?? []) as Issue[]).filter((i) => i.chat_active);
  const openReturns = ((returnsQuery.data ?? []) as ReturnItem[]).filter(
    (r) => !CLOSED_RETURNS.has(r.status)
  );

  const todayCount =
    dashboard.data?.orders_today ??
    orders.filter(
      (o) => parseApiDate(o.order_date).toDateString() === new Date().toDateString()
    ).length;

  // Stan maskotki jest POCHODNĄ DANYCH (sekcja 6): synchronizacja bije
  // z fazy cyklu, alarm z otwartych dyskusji, sen z pustego biurka.
  const state: OrdlakState =
    phase === "working"
      ? "sync"
      : phase === "success"
        ? "happy"
        : openIssues.length > 0
          ? "alert"
          : pending.length === 0
            ? "sleep"
            : "idle";

  // Tytuł karty mówi STAN, a nie "Cześć". Każdy wariant da się wskazać
  // palcem w danych, które ekran właśnie pokazuje.
  const cardTitle =
    phase === "working"
      ? "Synchronizuję Allegro"
      : openIssues.length > 0
        ? "Ktoś czeka na odpowiedź"
        : pending.length > 0
          ? "Są paczki do spakowania"
          : "Wszystko wysłane";

  const cardBody =
    phase === "working"
      ? "Pobieram zamówienia i zwroty z Allegro. Chwilę to potrwa."
      : openIssues.length > 0
        ? `${openIssues.length === 1 ? "Jedna dyskusja jest" : `${openIssues.length} dyskusje są`} otwarte. Odpowiedz, zanim kupujący zdąży się zniecierpliwić.`
        : pending.length > 0
          ? `${pending.length === 1 ? "Jedno zamówienie czeka" : `${pending.length} zamówień czeka`} na spakowanie. Pakowanie zatwierdzisz na desktopie.`
          : "Zero zaległości. Dotknij, żeby sprawdzić kanały jeszcze raz.";

  const refreshing =
    ordersQuery.isRefetching || issuesQuery.isRefetching || dashboard.isRefetching;

  return (
    <View style={styles.screen}>
      <TabHeading title="Start" accent="Start" count="Dziś" />

      <View style={styles.fadeWrap}>
        <ScrollView
          contentContainerStyle={styles.content}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={sync}
              tintColor={c.acc}
              colors={[c.acc]}
            />
          }
        >
          {/* ------------------------------------------ karta Ordlaka */}
          <Pressable
            onPress={sync}
            disabled={phase !== "idle"}
            accessibilityRole="button"
            accessibilityLabel="Synchronizuj z Allegro"
            style={({ pressed }) => [styles.ordCard, pressed && styles.pressed]}
          >
            {/* Poświata - jedno źródło światła, wycięte przez overflow karty. */}
            <LinearGradient
              colors={[c.accDim, "transparent"]}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 1 }}
              style={styles.ordGlow}
              pointerEvents="none"
            />
            <Ordlak state={state} size={62} />
            <View style={styles.ordCopy}>
              <Text style={styles.ordTitle} numberOfLines={1}>
                {cardTitle}
              </Text>
              <Text style={styles.ordBody}>{cardBody}</Text>
            </View>
          </Pressable>

          {/* ------------------------------------------------- kafle */}
          <View style={styles.tiles}>
            <Tile
              label="Do spakowania"
              value={String(pending.length)}
              tint="coral"
              delta={pending.length > 0 ? "czeka" : "czysto"}
              onPress={() => navigation.navigate("Main", { screen: "Orders" })}
            />
            <Tile
              label="Wartość dziś"
              value={formatMoney(dashboard.data?.revenue_today ?? 0, "PLN", { round: true }).replace(" zł", "")}
              unit="zł"
              tint="acc"
              delta={`${todayCount} ${todayCount === 1 ? "zamówienie" : "zamówień"}`}
            />
            <Tile
              label="Dyskusje"
              value={String(openIssues.length)}
              tint="violet"
              delta={openIssues.length > 0 ? "czeka na odpowiedź" : "nikt nie pyta"}
              onPress={() => navigation.navigate("Discussions")}
            />
            <Tile
              label="Zwroty"
              value={String(openReturns.length)}
              tint="amber"
              delta={openReturns.length > 0 ? "do obsłużenia" : "brak"}
              onPress={() => navigation.navigate("Returns")}
            />
          </View>

          {/* -------------------------------------- wymaga uwagi */}
          {pending.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Wymaga uwagi</Text>
              {pending.slice(0, 4).map((order) => (
                <OrderRow
                  key={order.external_id}
                  order={order}
                  onPress={() =>
                    navigation.navigate("OrderDetail", { externalId: order.external_id })
                  }
                />
              ))}
            </View>
          )}
        </ScrollView>

        {/* Wygaszenie u dołu - ucięta lista nie ma wyglądać na błąd. */}
        <LinearGradient
          colors={["transparent", c.bg]}
          style={styles.fade}
          pointerEvents="none"
        />
      </View>
    </View>
  );
}

const createStyles = (c: Palette) =>
  StyleSheet.create({
    screen: {
      flex: 1,
      backgroundColor: c.bg,
    },
    fadeWrap: {
      flex: 1,
      minHeight: 0,
    },
    content: {
      paddingHorizontal: spacing.xl,
      paddingBottom: 30,
      gap: 13,
    },
    fade: {
      position: "absolute",
      left: 0,
      right: 0,
      bottom: 0,
      height: 30,
    },
    pressed: {
      opacity: 0.85,
    },

    ordCard: {
      flexDirection: "row",
      alignItems: "center",
      gap: 14,
      borderRadius: radii.sheet,
      backgroundColor: c.card,
      borderWidth: 1,
      borderColor: c.line,
      paddingVertical: 16,
      paddingHorizontal: 18,
      overflow: "hidden",
    },
    ordGlow: {
      position: "absolute",
      left: -30,
      top: -40,
      width: 200,
      height: 180,
      borderRadius: 100,
    },
    ordCopy: {
      flex: 1,
      minWidth: 0,
      gap: 4,
    },
    ordTitle: {
      ...fonts.cardTitle,
      color: c.tx,
    },
    ordBody: {
      ...fonts.body,
      color: c.tx2,
    },

    tiles: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: 10,
    },
    tile: {
      // Dwie kolumny: połowa szerokości minus połowa odstępu.
      flexBasis: "48%",
      flexGrow: 1,
      borderRadius: radii.card,
      backgroundColor: c.card,
      borderWidth: 1,
      borderColor: c.line,
      paddingVertical: 14,
      paddingHorizontal: 15,
      gap: 6,
    },
    tileLabelRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
    },
    dot: {
      width: 5,
      height: 5,
      borderRadius: 2.5,
    },
    tileLabel: {
      ...fonts.eyebrow,
      fontSize: 9,
      color: c.tx3,
      flexShrink: 1,
    },
    tileValueRow: {
      flexDirection: "row",
      alignItems: "baseline",
    },
    tileValue: {
      ...fonts.kpi,
      color: c.tx,
    },
    tileUnit: {
      ...fonts.rowName,
      fontSize: 12.5,
      color: c.tx2,
      marginLeft: 1,
    },
    tileDelta: {
      ...fonts.mono,
      fontSize: 10,
      color: c.tx3,
    },

    section: {
      gap: spacing.sm,
      marginTop: 4,
    },
    sectionTitle: {
      ...fonts.panelTitle,
      color: c.tx,
      marginBottom: 2,
    },
  });
