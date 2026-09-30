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
import {
  Animated,
  Easing,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { withAlpha, type Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { fonts, radii, spacing } from "@/theme/typography";
import { TabHeading } from "@/components/TabHeading";
import { Ordlak, type OrdlakState } from "@/components/Ordlak";
import { OrderRow } from "@/components/OrderRow";
import { CountUp } from "@/components/CountUp";
import { useDashboard, useIssues, useOrders, useReturns } from "@/api/hooks";
import { useSync, type SyncPhase } from "@/store/sync";
import {
  formatMoney,
  isOpenReturn,
  isPendingFulfillment,
  lastSyncLabel,
  parseApiDate,
  plural,
} from "@/utils/format";
import { useNewIds } from "@/utils/useNewIds";
import type { Issue, Order, ReturnItem } from "@/api/types";
import type { RootStackParamList } from "@/navigation/types";

type Tint = "acc" | "coral" | "violet" | "amber";

function Tile({
  label,
  value,
  format,
  unit,
  delta,
  tint,
  onPress,
}: {
  label: string;
  value: number;
  format?: (value: number) => string;
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
        <CountUp value={value} format={format} style={styles.tileValue} numberOfLines={1} />
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

/**
 * Postęp synchronizacji - karta Ordlaka wypełnia się od lewej do prawej.
 *
 * Wcześniej karta miała stałą poświatę w lewym górnym rogu. Jej
 * zaokrąglona krawędź kończyła się mniej więcej w połowie karty, więc
 * na telefonie czytała się jak pasek postępu zatrzymany na 45% - także
 * wtedy, gdy nic się nie działo. Karta w spoczynku jest teraz gładka,
 * a wypełnienie pojawia się WYŁĄCZNIE w trakcie synchronizacji.
 *
 * `/orders/sync` nie raportuje postępu, więc wypełnienie jest uczciwie
 * niepewne: szybko do 70%, potem pełznie ku 94% i dopiero odpowiedź
 * serwera domyka je do 100%. Nieudana synchronizacja nie domyka paska -
 * gaśnie tam, gdzie stanął.
 */
function SyncSweep({ phase }: { phase: SyncPhase }) {
  const styles = useThemedStyles(createStyles);
  const { c, reduceMotion } = useTheme();
  const [width, setWidth] = React.useState(0);
  const progress = React.useRef(new Animated.Value(0)).current;
  const opacity = React.useRef(new Animated.Value(0)).current;

  React.useEffect(() => {
    const timing = (value: Animated.Value, toValue: number, duration: number, easing = Easing.linear) =>
      Animated.timing(value, {
        toValue,
        duration: reduceMotion ? 0 : duration,
        easing,
        useNativeDriver: true,
      });

    let animation: Animated.CompositeAnimation;
    if (phase === "working") {
      progress.setValue(0);
      opacity.setValue(1);
      animation = Animated.sequence([
        timing(progress, 0.7, 1400, Easing.out(Easing.cubic)),
        timing(progress, 0.94, 14000, Easing.out(Easing.quad)),
      ]);
    } else if (phase === "success") {
      // Domknięcie + chwila na zobaczenie pełnego paska. Razem 1620 ms,
      // mieści się w fazie sukcesu (1900 ms w `store/sync`).
      animation = Animated.sequence([
        timing(progress, 1, 320, Easing.out(Easing.cubic)),
        Animated.delay(reduceMotion ? 0 : 700),
        timing(opacity, 0, 600),
      ]);
    } else {
      // Spoczynek: po sukcesie pasek już zgasł, po porażce gaśnie teraz.
      animation = timing(opacity, 0, 260);
    }
    animation.start();
    return () => animation.stop();
  }, [phase, reduceMotion, progress, opacity]);

  // Warstwa ma szerokość karty i wjeżdża z lewej (`translateX`), a nie
  // rośnie (`width`) - przesunięcie idzie natywnym sterownikiem.
  const translateX = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [-width, 0],
  });

  return (
    <View
      style={StyleSheet.absoluteFill}
      pointerEvents="none"
      onLayout={(event) => setWidth(event.nativeEvent.layout.width)}
    >
      <Animated.View style={[StyleSheet.absoluteFill, { opacity, transform: [{ translateX }] }]}>
        {/* Wypełnienie gęstnieje ku czołu - wiadomo, w którą stronę idzie. */}
        <LinearGradient
          colors={[withAlpha(c.acc, 0.03), withAlpha(c.acc, 0.13)]}
          start={{ x: 0, y: 0.5 }}
          end={{ x: 1, y: 0.5 }}
          style={StyleSheet.absoluteFill}
        />
        <View style={[styles.sweepBar, { backgroundColor: c.acc }]} />
      </Animated.View>
    </View>
  );
}

export function StartScreen() {
  const styles = useThemedStyles(createStyles);
  const { c } = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { phase, subtitle, sync } = useSync();

  const dashboard = useDashboard();
  const ordersQuery = useOrders();
  const issuesQuery = useIssues();
  const returnsQuery = useReturns();

  const orders = (ordersQuery.data ?? []) as Order[];
  const pending = orders.filter(isPendingFulfillment);
  const openIssues = ((issuesQuery.data ?? []) as Issue[]).filter((i) => i.chat_active);
  const openReturns = ((returnsQuery.data ?? []) as ReturnItem[]).filter(isOpenReturn);

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
      : phase === "success"
        ? "Zsynchronizowano"
        : openIssues.length > 0
        ? "Ktoś czeka na odpowiedź"
        : pending.length > 0
          ? "Są paczki do spakowania"
          : "Wszystko wysłane";

  const cardBody =
    phase === "working"
      ? "Pobieram zamówienia i zwroty z Allegro. Chwilę to potrwa."
      : phase === "success"
        ? subtitle
        : openIssues.length > 0
        ? `${
            openIssues.length === 1
              ? "Jedna dyskusja jest otwarta"
              : `${openIssues.length} ${plural(openIssues.length, "dyskusja jest otwarta", "dyskusje są otwarte", "dyskusji jest otwartych")}`
          }. Odpowiedz, zanim kupujący zdąży się zniecierpliwić.`
        : pending.length > 0
          ? `${
              pending.length === 1
                ? "Jedno zamówienie czeka"
                : `${pending.length} ${plural(pending.length, "zamówienie czeka", "zamówienia czekają", "zamówień czeka")}`
            } na spakowanie. Pakowanie zatwierdzisz na desktopie.`
          : "Zero zaległości. Dotknij, żeby sprawdzić kanały jeszcze raz.";

  const refreshing =
    ordersQuery.isRefetching || issuesQuery.isRefetching || dashboard.isRefetching;

  // "N min temu" ma się zmieniać także między odświeżeniami danych.
  const [, tick] = React.useReducer((n: number) => n + 1, 0);
  React.useEffect(() => {
    const timer = setInterval(tick, 30_000);
    return () => clearInterval(timer);
  }, []);
  const lastSync = lastSyncLabel(dashboard.data?.last_sync_human);

  const freshOrders = useNewIds(
    ordersQuery.data ? pending.map((o) => o.external_id) : undefined
  );

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
            <SyncSweep phase={phase} />
            <Ordlak state={state} size={62} />
            <View style={styles.ordCopy}>
              <Text style={styles.ordTitle} numberOfLines={1}>
                {cardTitle}
              </Text>
              <Text style={styles.ordBody}>{cardBody}</Text>
              {/* Pi synchronizuje samo co minutę - ta linia mówi, że to
                  działa, a kwadrans ciszy robi się koralowy. */}
              {phase === "idle" && lastSync ? (
                <Text
                  style={[styles.ordSync, lastSync.stale && { color: c.coral }]}
                  numberOfLines={1}
                >
                  {lastSync.text}
                </Text>
              ) : null}
            </View>
          </Pressable>

          {/* ------------------------------------------------- kafle */}
          <View style={styles.tiles}>
            <Tile
              label="Do spakowania"
              value={pending.length}
              tint="coral"
              delta={pending.length > 0 ? "czeka" : "czysto"}
              onPress={() => navigation.navigate("Main", { screen: "Orders" })}
            />
            <Tile
              label="Wartość dziś"
              value={Number(dashboard.data?.revenue_today ?? 0)}
              format={(v) => formatMoney(v, "PLN", { round: true }).replace(" zł", "")}
              unit="zł"
              tint="acc"
              delta={`${todayCount} ${plural(todayCount, "zamówienie", "zamówienia", "zamówień")}`}
            />
            <Tile
              label="Dyskusje"
              value={openIssues.length}
              tint="violet"
              delta={openIssues.length > 0 ? "czeka na odpowiedź" : "nikt nie pyta"}
              onPress={() => navigation.navigate("Discussions")}
            />
            <Tile
              label="Zwroty"
              value={openReturns.length}
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
                  highlight={freshOrders.has(order.external_id)}
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
    sweepBar: {
      position: "absolute",
      left: 0,
      right: 0,
      bottom: 0,
      height: 2,
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
    ordSync: {
      ...fonts.mono,
      fontSize: 10,
      color: c.tx3,
      marginTop: 2,
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
