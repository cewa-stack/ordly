/**
 * Dolna nawigacja (Start / Zamówienia / Magazyn / Zwroty / Dyskusje /
 * Skrzynka) - pasek pływający, przezroczysty z rozmyciem, zgodnie z §5
 * 02_appdesign.md. Aktywna zakładka = ikona i etykieta w kolorze primary
 * (Brand Teal), reszta wyciszona. Statystyki przeniesione do apki
 * desktopowej (pełne zarządzanie) - mobile to podgląd + push.
 */
import * as React from "react";
import { Platform, StyleSheet } from "react-native";
import { BlurView } from "expo-blur";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";

import { colors } from "@/theme/colors";
import { typography } from "@/theme/typography";
import { BoxIcon, ChatIcon, HomeIcon, MailIcon, ReceiptIcon, UndoIcon } from "@/icons";
import { HomeScreen } from "@/screens/HomeScreen";
import { OrdersScreen } from "@/screens/OrdersScreen";
import { StockScreen } from "@/screens/StockScreen";
import { ReturnsScreen } from "@/screens/ReturnsScreen";
import { DiscussionsScreen } from "@/screens/DiscussionsScreen";
import { MailboxScreen } from "@/screens/MailboxScreen";
import type { MainTabParamList } from "./types";

const Tab = createBottomTabNavigator<MainTabParamList>();

export function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: true,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textDim,
        tabBarLabelStyle: typography.tabLabel,
        tabBarStyle: styles.tabBar,
        tabBarBackground: () =>
          Platform.OS === "ios" ? (
            <BlurView intensity={40} tint="dark" style={StyleSheet.absoluteFill} />
          ) : null,
        tabBarItemStyle: styles.tabItem,
      }}
    >
      <Tab.Screen
        name="Home"
        component={HomeScreen}
        options={{
          title: "Start",
          tabBarIcon: ({ color, size }) => <HomeIcon color={color} size={size} />,
        }}
      />
      <Tab.Screen
        name="Orders"
        component={OrdersScreen}
        options={{
          title: "Zamówienia",
          tabBarIcon: ({ color, size }) => <ReceiptIcon color={color} size={size} />,
        }}
      />
      <Tab.Screen
        name="Stock"
        component={StockScreen}
        options={{
          title: "Magazyn",
          tabBarIcon: ({ color, size }) => <BoxIcon color={color} size={size} />,
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
      <Tab.Screen
        name="Discussions"
        component={DiscussionsScreen}
        options={{
          title: "Dyskusje",
          tabBarIcon: ({ color, size }) => <ChatIcon color={color} size={size} />,
        }}
      />
      <Tab.Screen
        name="Mailbox"
        component={MailboxScreen}
        options={{
          title: "Skrzynka",
          tabBarIcon: ({ color, size }) => <MailIcon color={color} size={size} />,
        }}
      />
    </Tab.Navigator>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    position: "absolute",
    left: 12,
    right: 12,
    bottom: 12,
    height: 62,
    borderRadius: 20,
    borderTopWidth: 1,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: Platform.OS === "ios" ? "transparent" : "rgba(22,27,34,0.97)",
    elevation: 0,
  },
  tabItem: {
    paddingTop: 9,
  },
});
