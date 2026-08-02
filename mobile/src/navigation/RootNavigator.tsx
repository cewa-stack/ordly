/**
 * Stos główny. Kolejność ekranów odpowiada stanowi z AuthProvider:
 * brak sesji -> Login, sesja zablokowana biometrią -> Lock, świeże
 * logowanie na sprzęcie z biometrią -> BiometricOptIn (raz), inaczej Main.
 * OrderDetail/StockItem/IssueDetail/MailDetail/Settings są pushowane NAD
 * tabami.
 */
import * as React from "react";
import { createNativeStackNavigator } from "@react-navigation/native-stack";

import { colors } from "@/theme/colors";
import { useAuth } from "@/store/auth";
import { LoginScreen } from "@/screens/LoginScreen";
import { LockScreen } from "@/screens/LockScreen";
import { BiometricOptInScreen } from "@/screens/BiometricOptInScreen";
import { OrderDetailScreen } from "@/screens/OrderDetailScreen";
import { SettingsScreen } from "@/screens/SettingsScreen";
import { StockItemScreen } from "@/screens/StockItemScreen";
import { IssueDetailScreen } from "@/screens/IssueDetailScreen";
import { MailDetailScreen } from "@/screens/MailDetailScreen";
import { MainTabs } from "./MainTabs";
import type { RootStackParamList } from "./types";

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator() {
  const { hasSession, isLocked, needsBiometricPrompt } = useAuth();

  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.background },
        headerTintColor: colors.text,
        headerShadowVisible: false,
        headerTitleStyle: { fontSize: 17, fontWeight: "600" },
        contentStyle: { backgroundColor: colors.background },
      }}
    >
      {!hasSession ? (
        <Stack.Screen name="Login" component={LoginScreen} options={{ headerShown: false }} />
      ) : isLocked ? (
        <Stack.Screen name="Lock" component={LockScreen} options={{ headerShown: false }} />
      ) : needsBiometricPrompt ? (
        <Stack.Screen
          name="BiometricOptIn"
          component={BiometricOptInScreen}
          options={{ headerShown: false }}
        />
      ) : (
        <>
          <Stack.Screen name="Main" component={MainTabs} options={{ headerShown: false }} />
          <Stack.Screen
            name="OrderDetail"
            component={OrderDetailScreen}
            options={{ title: "Zamówienie" }}
          />
          <Stack.Screen
            name="StockItem"
            component={StockItemScreen}
            options={{ title: "Produkt" }}
          />
          <Stack.Screen
            name="IssueDetail"
            component={IssueDetailScreen}
            options={{ title: "Dyskusja" }}
          />
          <Stack.Screen
            name="MailDetail"
            component={MailDetailScreen}
            options={{ title: "Wiadomość" }}
          />
          <Stack.Screen
            name="Settings"
            component={SettingsScreen}
            options={{ title: "Ustawienia" }}
          />
        </>
      )}
    </Stack.Navigator>
  );
}
