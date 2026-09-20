/**
 * Punkt wejścia aplikacji ORDLY Mobile.
 *
 * Kolejność providerów ma znaczenie:
 * - SafeAreaProvider na zewnątrz (nawigacja i ekrany czytają insets),
 * - ThemeProvider NAD wszystkim, co rysuje - łącznie z ekranem startowym,
 *   bo Ordlak czyta z niego paletę,
 * - AuthProvider NAD NavigationContainer, bo RootNavigator decyduje
 *   Login vs Main na podstawie `useAuth()`.
 *
 * Motyw nawigacji i styl paska stanu biorą się z AKTYWNEJ atmosfery
 * (sekcja 11) - stąd osobny komponent `ThemedApp` pod ThemeProviderem.
 */
import * as React from "react";
import { StyleSheet, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { NavigationContainer } from "@react-navigation/native";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { useFonts } from "expo-font";
import {
  BricolageGrotesque_700Bold,
} from "@expo-google-fonts/bricolage-grotesque";
import {
  InstrumentSans_400Regular,
  InstrumentSans_500Medium,
  InstrumentSans_600SemiBold,
} from "@expo-google-fonts/instrument-sans";
import {
  JetBrainsMono_500Medium,
  JetBrainsMono_600SemiBold,
} from "@expo-google-fonts/jetbrains-mono";

import { AuthProvider, useAuth } from "@/store/auth";
import { ThemeProvider, useTheme } from "@/theme/theme";
import { navigationThemeFor } from "@/navigation/theme";
import { RootNavigator } from "@/navigation/RootNavigator";
import { Ordlak } from "@/components/Ordlak";
import { injectPwaHeadTags, registerServiceWorker } from "@/push/webPush";
import { SyncProvider } from "@/store/sync";

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

/** Ekran ładowania przy starcie (odczyt sesji) - marka zamiast pustej klatki. */
function SplashGate({ children }: { children: React.ReactNode }) {
  const { isLoading } = useAuth();
  const { c } = useTheme();
  if (isLoading) {
    return (
      <View style={[styles.splash, { backgroundColor: c.bg }]}>
        {/* Wczytywanie to praca, nie spoczynek - stąd `sync`, nie `idle`. */}
        <Ordlak state="sync" size={84} />
      </View>
    );
  }
  return <>{children}</>;
}

function ThemedApp() {
  const { c, mode } = useTheme();
  /**
   * Kroje ladowane LOKALNIE z bundla (pliki .ttf z paczek
   * `@expo-google-fonts/*`) - bez zapytania do sieci, wiec aplikacja
   * wyglada tak samo bez internetu. Klucze musza sie zgadzac z
   * `family` w theme/typography.ts.
   */
  const [fontsReady, fontError] = useFonts({
    BricolageGrotesque_700Bold,
    InstrumentSans_400Regular,
    InstrumentSans_500Medium,
    InstrumentSans_600SemiBold,
    JetBrainsMono_500Medium,
    JetBrainsMono_600SemiBold,
  });
  const navTheme = React.useMemo(() => navigationThemeFor(c, mode), [c, mode]);

  // Blad wczytania krojow NIE blokuje aplikacji - lepiej pokazac ekrany
  // systemowym krojem niz nie pokazac ich wcale.
  if (!fontsReady && !fontError) {
    return <View style={[styles.splash, { backgroundColor: c.bg }]} />;
  }

  return (
    <View style={[styles.root, { backgroundColor: c.bg }]}>
      <AuthProvider>
        <SplashGate>
          <NavigationContainer theme={navTheme}>
            {/*
              Ikony paska stanu muszą być odwrotnością podłoża: ciemne na
              atmosferze dziennej, jasne na nocnej. Na sztywno "dark"
              znikałyby po zapadnięciu nocy.
            */}
            <StatusBar style={mode === "day" ? "dark" : "light"} />
            <SyncProvider>
              <RootNavigator />
            </SyncProvider>
          </NavigationContainer>
        </SplashGate>
      </AuthProvider>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  splash: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
});

export default function App() {
  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <ThemedApp />
        </ThemeProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
