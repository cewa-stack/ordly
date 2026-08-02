/**
 * Punkt wejścia aplikacji ORDLY Mobile.
 *
 * Kolejność providerów ma znaczenie: SafeAreaProvider musi być na zewnątrz
 * (nawigacja i ekrany czytają insets), AuthProvider musi być NAD
 * NavigationContainer, bo RootNavigator decyduje Login vs Main na
 * podstawie `useAuth()`.
 */
import * as React from "react";
import { StyleSheet, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { NavigationContainer } from "@react-navigation/native";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { colors } from "@/theme/colors";
import { AuthProvider, useAuth } from "@/store/auth";
import { navigationTheme } from "@/navigation/theme";
import { RootNavigator } from "@/navigation/RootNavigator";
import { Mascot } from "@/components/Mascot";
import { injectPwaHeadTags, registerServiceWorker } from "@/push/webPush";

// Efekt uboczny na `document` - no-op na natywnym iOS/Android (guard w środku).
injectPwaHeadTags();
void registerServiceWorker();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 15_000,
    },
  },
});

/** Ekran ładowania przy starcie (odczyt sesji z SecureStore) - marka zamiast pustej klatki. */
function SplashGate({ children }: { children: React.ReactNode }) {
  const { isLoading } = useAuth();
  if (isLoading) {
    return (
      <View style={styles.splash}>
        <Mascot size={72} />
      </View>
    );
  }
  return <>{children}</>;
}

const styles = StyleSheet.create({
  splash: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.background,
  },
});

export default function App() {
  return (
    <SafeAreaProvider style={{ backgroundColor: colors.background }}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <SplashGate>
            <NavigationContainer theme={navigationTheme}>
              <StatusBar style="light" />
              <RootNavigator />
            </NavigationContainer>
          </SplashGate>
        </AuthProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
