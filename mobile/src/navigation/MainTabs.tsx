/**
 * Pięć zakładek (sekcja 11 instrukcji "Nokturn"):
 *
 *   Start · Zamówienia · ORDLAK · Magazyn · Poczta
 *
 * Środkowa zakładka jest wejściem do asystenta i JEDNOCZEŚNIE pokazuje
 * jego stan. Dyskusje i Zwroty zeszły z paska - nie zniknęły: prowadzą
 * do nich kafle i lista "Wymaga uwagi" na ekranie Start, a w stosie
 * głównym są zwykłymi ekranami z nagłówkiem.
 *
 * ARYTMETYKA GAŁKI, której nie wolno ruszyć:
 *
 *   margin-top: -24  +  wysokość 54  +  margin-top etykiety 4  =  34
 *
 * 34 px to dokładnie tyle, ile mają od góry paska etykiety pozostałych
 * zakładek (padding-top 8 + ikona 21 + gap 5). Zmiana JEDNEJ z tych
 * trzech liczb rozstraja pasek.
 *
 * Pierścień gałki ma JEDNO znaczenie: coś wymaga uwagi. Synchronizacji
 * pierścień NIE pokazuje - niesie ją antena maskotki. Jeden sygnał ma
 * jedno miejsce; dwa naraz w kółku o średnicy 54 px to szum.
 */
import * as React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { createBottomTabNavigator, type BottomTabBarProps } from "@react-navigation/bottom-tabs";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { fonts } from "@/theme/typography";
import { BoxIcon, HomeIcon, MailIcon, ReceiptIcon } from "@/icons";
import { Ordlak, type OrdlakState } from "@/components/Ordlak";
import { StartScreen } from "@/screens/StartScreen";
import { OrdersScreen } from "@/screens/OrdersScreen";
import { OrdlakScreen } from "@/screens/OrdlakScreen";
import { StockScreen } from "@/screens/StockScreen";
import { MailboxScreen } from "@/screens/MailboxScreen";
import { useIssues, useMailMessages, useOrders } from "@/api/hooks";
import { useSync } from "@/store/sync";
import { isPendingFulfillment } from "@/utils/format";
import type { Issue, MailMessage, Order } from "@/api/types";
import type { MainTabParamList } from "./types";

const Tab = createBottomTabNavigator<MainTabParamList>();

/** Wysokość paska bez marginesu bezpiecznego (sekcja 11). */
const BAR_HEIGHT = 88;
const ICON_SIZE = 21;

type TabKey = keyof MainTabParamList;

const TAB_ICON: Record<Exclude<TabKey, "Ordlak">, (color: string) => React.ReactNode> = {
  Home: (color) => <HomeIcon size={ICON_SIZE} color={color} />,
  Orders: (color) => <ReceiptIcon size={ICON_SIZE} color={color} />,
  Stock: (color) => <BoxIcon size={ICON_SIZE} color={color} />,
  Mailbox: (color) => <MailIcon size={ICON_SIZE} color={color} />,
};

const TAB_LABEL: Record<TabKey, string> = {
  Home: "Start",
  Orders: "Zamówienia",
  Ordlak: "Ordlak",
  Stock: "Magazyn",
  Mailbox: "Poczta",
};

/** Odznaka liczbowa - liczy WYŁĄCZNIE sprawy wymagające decyzji. */
function TabBadge({ count, styles }: { count: number; styles: Styles }) {
  if (count <= 0) return null;
  return (
    <View style={styles.badge}>
      <Text style={styles.badgeText}>{count > 99 ? "99+" : count}</Text>
    </View>
  );
}

/**
 * Własny pasek zakładek. Domyślny nie umie wypuścić gałki ponad swoją
 * krawędź (obcina ją `overflow`), a bez tego środkowa zakładka jest
 * zwykłym kółkiem wklejonym w pasek.
 */
function TabBar({ state, navigation }: BottomTabBarProps) {
  const styles = useThemedStyles(createStyles);
  const { c } = useTheme();
  const insets = useSafeAreaInsets();
  const { phase } = useSync();

  const orders = useOrders();
  const issues = useIssues();
  const mail = useMailMessages();

  const pendingOrders = ((orders.data ?? []) as Order[]).filter(isPendingFulfillment).length;
  const openIssues = ((issues.data ?? []) as Issue[]).filter((issue) => issue.chat_active).length;
  const unreadMail = ((mail.data ?? []) as MailMessage[]).filter((m) => !m.is_read).length;

  const badges: Record<string, number> = {
    Orders: pendingOrders,
    Mailbox: unreadMail,
  };

  // Alarm gałki: coś czeka na użytkownika. Synchronizacja NIE zapala
  // pierścienia - niesie ją antena maskotki.
  const needsAttention = openIssues > 0;
  const ordlakState: OrdlakState =
    phase === "working" ? "sync" : needsAttention ? "alert" : phase === "success" ? "happy" : "idle";

  return (
    <View style={[styles.bar, { paddingBottom: insets.bottom }]}>
      {state.routes.map((route, index) => {
        const focused = state.index === index;
        const key = route.name as TabKey;
        const label = TAB_LABEL[key];

        function onPress() {
          const event = navigation.emit({
            type: "tabPress",
            target: route.key,
            canPreventDefault: true,
          });
          if (!focused && !event.defaultPrevented) {
            navigation.navigate(route.name);
          }
        }

        if (key === "Ordlak") {
          return (
            <Pressable
              key={route.key}
              onPress={onPress}
              accessibilityRole="button"
              accessibilityState={{ selected: focused }}
              accessibilityLabel={
                needsAttention ? "Ordlak - coś wymaga uwagi" : "Ordlak - asystent"
              }
              style={styles.tabOrd}
            >
              <View
                style={[
                  styles.knob,
                  focused && { backgroundColor: c.accDim, borderColor: "transparent" },
                  needsAttention && { borderColor: c.coral, borderWidth: 2 },
                ]}
              >
                <Ordlak state={ordlakState} size={40} />
              </View>
              <Text
                style={[
                  styles.knobLabel,
                  focused && { color: c.acc, fontFamily: fonts.rowName.fontFamily },
                  needsAttention && { color: c.coral, fontFamily: fonts.rowName.fontFamily },
                ]}
              >
                {label}
              </Text>
            </Pressable>
          );
        }

        const color = focused ? c.acc : c.tx3;
        return (
          <Pressable
            key={route.key}
            onPress={onPress}
            accessibilityRole="button"
            accessibilityState={{ selected: focused }}
            accessibilityLabel={label}
            style={styles.tab}
          >
            <View>
              {TAB_ICON[key as Exclude<TabKey, "Ordlak">](color)}
              <TabBadge count={badges[key] ?? 0} styles={styles} />
            </View>
            <Text style={[styles.label, { color }]} numberOfLines={1}>
              {label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function MainTabs() {
  return (
    <Tab.Navigator
      tabBar={(props) => <TabBar {...props} />}
      sceneContainerStyle={{ backgroundColor: "transparent" }}
      screenOptions={{ headerShown: false }}
    >
      <Tab.Screen name="Home" component={StartScreen} />
      <Tab.Screen name="Orders" component={OrdersScreen} />
      <Tab.Screen name="Ordlak" component={OrdlakScreen} />
      <Tab.Screen name="Stock" component={StockScreen} />
      <Tab.Screen name="Mailbox" component={MailboxScreen} />
    </Tab.Navigator>
  );
}

type Styles = ReturnType<typeof createStyles>;

const createStyles = (c: Palette) =>
  StyleSheet.create({
    bar: {
      flexDirection: "row",
      alignItems: "flex-start",
      height: BAR_HEIGHT,
      paddingTop: 10,
      paddingHorizontal: 14,
      borderTopWidth: 1,
      borderTopColor: c.line,
      backgroundColor: c.card,
      // Gałka wystaje 14 px ponad pasek - `overflow: visible` jest
      // domyślne na iOS, ale Android przycina bez tego.
      overflow: "visible",
    },
    tab: {
      flex: 1,
      alignItems: "center",
      gap: 5,
      paddingTop: 8,
      // Pole trafienia: 8 + 21 + 5 + 13 = 47 px wysokości, ponad
      // wymagane 44 x 44 (sekcja 14).
      minHeight: 47,
    },
    label: {
      ...fonts.tabLabel,
    },
    tabOrd: {
      width: 74,
      alignItems: "center",
    },
    knob: {
      width: 54,
      height: 54,
      borderRadius: 27,
      // Wystaje 14 px ponad pasek: -24 + 10 (padding-top paska) = -14.
      marginTop: -24,
      backgroundColor: c.card,
      borderWidth: 1,
      borderColor: c.line2,
      alignItems: "center",
      justifyContent: "center",
      shadowColor: c.shadow,
      shadowOpacity: 1,
      shadowRadius: 24,
      shadowOffset: { width: 0, height: 10 },
      elevation: 6,
    },
    knobLabel: {
      ...fonts.tabLabel,
      color: c.tx3,
      marginTop: 4,
    },
    badge: {
      position: "absolute",
      top: -5,
      right: -9,
      minWidth: 14,
      height: 14,
      paddingHorizontal: 4,
      borderRadius: 7,
      backgroundColor: c.coral,
      borderWidth: 2,
      borderColor: c.card,
      alignItems: "center",
      justifyContent: "center",
    },
    badgeText: {
      ...fonts.tabLabel,
      fontSize: 8.5,
      lineHeight: 10,
      color: c.bg,
    },
  });
