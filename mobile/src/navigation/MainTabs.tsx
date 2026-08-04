/**
 * Pięć zakładek podglądu wg sekcji 6.2 specyfikacji: Zamówienia,
 * Dyskusje, Magazyn, Poczta, Zwroty.
 *
 * ZMIANA WOBEC POPRZEDNIEJ WERSJI: zakładka "Start" zniknęła. Jej rolę
 * przejął wspólny nagłówek (`AppHeader`) widoczny nad każdą zakładką -
 * powitanie, Ordi i pigułka synchronizacji. Sekcja 6.1 pokazuje dokładnie
 * taki układ, a osobny ekran startowy dublował dane, które i tak widać
 * w zakładkach.
 *
 * Pasek jest PŁYWAJĄCY: 13 px od krawędzi, wysokość 62 px, promień 21,
 * białe tło z rozmyciem (sekcja 6.1). Treść zakładki ma dolny odstęp
 * 96 px, żeby ostatnia karta nie chowała się pod paskiem.
 *
 * Odznaki liczbowe liczą WYŁĄCZNIE sprawy wymagające decyzji - te same,
 * które liczy plakietka aplikacji (sekcja 04 koncepcji push). Przeczytane
 * maile i zamknięte zwroty się nie liczą.
 */
import * as React from "react";
import { Platform, StyleSheet, Text, View } from "react-native";
import { BlurView } from "expo-blur";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";

import { colors } from "@/theme/colors";
import { radii, typography } from "@/theme/typography";
import { BoxIcon, ChatIcon, MailIcon, ReceiptIcon, UndoIcon } from "@/icons";
import { OrdersScreen } from "@/screens/OrdersScreen";
import { StockScreen } from "@/screens/StockScreen";
import { ReturnsScreen } from "@/screens/ReturnsScreen";
import { DiscussionsScreen } from "@/screens/DiscussionsScreen";
import { MailboxScreen } from "@/screens/MailboxScreen";
import { useIssues, useMailMessages, useOrders, useStock } from "@/api/hooks";
import { isPendingFulfillment } from "@/utils/format";
import type { Issue, MailMessage, Order, StockItem } from "@/api/types";
import type { MainTabParamList } from "./types";

const Tab = createBottomTabNavigator<MainTabParamList>();

/** Odznaka na zakładce: min. 14 px, tło coral, biała obwódka 2 px (sekcja 6.1). */
function TabBadge({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <View style={styles.badge}>
      <Text style={styles.badgeText}>{count > 99 ? "99+" : count}</Text>
    </View>
  );
}

export function MainTabs() {
  const orders = useOrders();
  const issues = useIssues();
  const stock = useStock();
  const mail = useMailMessages();

  const pendingOrders = ((orders.data ?? []) as Order[]).filter((order) =>
    isPendingFulfillment(order.fulfillment_status)
  ).length;
  const openIssues = ((issues.data ?? []) as Issue[]).filter((issue) => issue.chat_active).length;
  const lowStock = ((stock.data ?? []) as StockItem[]).filter((item) => item.is_low_stock).length;
  const unreadMail = ((mail.data ?? []) as MailMessage[]).filter(
    (message) => !message.is_read
  ).length;

  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: true,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textOnIcon,
        tabBarLabelStyle: typography.tabLabel,
        tabBarStyle: styles.tabBar,
        tabBarBackground: () =>
          Platform.OS === "ios" ? (
            <BlurView intensity={30} tint="light" style={StyleSheet.absoluteFill} />
          ) : null,
        tabBarItemStyle: styles.tabItem,
      }}
    >
      <Tab.Screen
        name="Orders"
        component={OrdersScreen}
        options={{
          title: "Zamówienia",
          tabBarIcon: ({ color, size }) => (
            <View>
              <ReceiptIcon color={color} size={size} />
              <TabBadge count={pendingOrders} />
            </View>
          ),
        }}
      />
      <Tab.Screen
        name="Discussions"
        component={DiscussionsScreen}
        options={{
          title: "Dyskusje",
          tabBarIcon: ({ color, size }) => (
            <View>
              <ChatIcon color={color} size={size} />
              <TabBadge count={openIssues} />
            </View>
          ),
        }}
      />
      <Tab.Screen
        name="Stock"
        component={StockScreen}
        options={{
          title: "Magazyn",
          tabBarIcon: ({ color, size }) => (
            <View>
              <BoxIcon color={color} size={size} />
              <TabBadge count={lowStock} />
            </View>
          ),
        }}
      />
      <Tab.Screen
        name="Mailbox"
        component={MailboxScreen}
        options={{
          title: "Poczta",
          tabBarIcon: ({ color, size }) => (
            <View>
              <MailIcon color={color} size={size} />
              <TabBadge count={unreadMail} />
            </View>
          ),
        }}
      />
      <Tab.Screen
        name="Returns"
        component={ReturnsScreen}
        options={{
          title: "Zwroty",
          tabBarIcon: ({ color, size }) => <UndoIcon color={color} size={size} />,
        }}
      />
    </Tab.Navigator>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    position: "absolute",
    left: 13,
    right: 13,
    bottom: 13,
    height: 62,
    borderRadius: radii.xl,
    borderTopWidth: 1,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: Platform.OS === "ios" ? "rgba(255,255,255,0.92)" : "rgba(255,255,255,0.97)",
    shadowColor: "#232B27",
    shadowOpacity: 0.3,
    shadowRadius: 32,
    shadowOffset: { width: 0, height: 12 },
    elevation: 8,
  },
  tabItem: {
    paddingTop: 7,
  },
  badge: {
    position: "absolute",
    top: -5,
    right: -9,
    minWidth: 14,
    height: 14,
    paddingHorizontal: 4,
    borderRadius: 8,
    backgroundColor: "#FF8563",
    borderWidth: 2,
    borderColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
  },
  badgeText: {
    fontSize: 8.5,
    fontWeight: "600",
    color: "#FFFFFF",
    lineHeight: 10,
  },
});
