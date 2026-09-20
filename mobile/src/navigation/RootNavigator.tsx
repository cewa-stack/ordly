/**
 * Stos główny. Kolejność ekranów odpowiada stanowi z AuthProvider:
 * brak sesji -> Login, sesja zablokowana biometrią -> Lock, świeże
 * logowanie na sprzęcie z biometrią -> BiometricOptIn (raz), inaczej Main.
 * OrderDetail/IssueDetail/MailDetail/Settings są pushowane NAD tabami.
 */
import * as React from "react";
import { createNativeStackNavigator } from "@react-navigation/native-stack";

import type { Palette } from "@/theme/colors";
import { useTheme } from "@/theme/theme";
import { useAuth } from "@/store/auth";
import { LoginScreen } from "@/screens/LoginScreen";
import { LockScreen } from "@/screens/LockScreen";
import { BiometricOptInScreen } from "@/screens/BiometricOptInScreen";
import { OrderDetailScreen } from "@/screens/OrderDetailScreen";
import { SettingsScreen } from "@/screens/SettingsScreen";
import { IssueDetailScreen } from "@/screens/IssueDetailScreen";
import { MailDetailScreen } from "@/screens/MailDetailScreen";
import { DiscussionsScreen } from "@/screens/DiscussionsScreen";
import { ReturnsScreen } from "@/screens/ReturnsScreen";
import { MainShell } from "./MainShell";
import { usePushDeepLinks } from "./usePushDeepLinks";
import type { RootStackParamList } from "./types";

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator() {
  const { c } = useTheme();
  const { hasSession, isLocked, needsBiometricPrompt } = useAuth();

  // Wejście z powiadomienia w konkretny rekord. Podpinane tylko przy
  // odblokowanej sesji - inaczej push otwierałby ekran szczegółów nad
  // ekranem logowania.
  usePushDeepLinks(hasSession && !isLocked && !needsBiometricPrompt);

  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: c.bg },
        headerTintColor: c.tx,
        headerShadowVisible: false,
        headerTitleStyle: { fontSize: 17, fontWeight: "600" },
        contentStyle: { backgroundColor: c.bg },
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
          <Stack.Screen name="Main" component={MainShell} options={{ headerShown: false }} />
          <Stack.Screen
            name="OrderDetail"
            component={OrderDetailScreen}
            options={{ title: "Zamówienie" }}
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
          {/*
            Dyskusje i Zwroty zeszly z paska zakladek (sekcja 11), ale
            NIE sa slepymi zaulkami: prowadza do nich kafle na ekranie
            Start oraz powiadomienia push.
          */}
          <Stack.Screen
            name="Discussions"
            component={DiscussionsScreen}
            options={{ title: "Dyskusje" }}
          />
          <Stack.Screen
            name="Returns"
            component={ReturnsScreen}
            options={{ title: "Zwroty" }}
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
