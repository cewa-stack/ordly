/**
 * Szkielet aplikacji mobilnej (sekcja 11 instrukcji "Nokturn"):
 *
 *   pasek stanu systemu
 *   -------------------------
 *   zawartość zakładki (własny nagłówek + treść)
 *   -------------------------
 *   pasek zakładek (88 px, z gałką Ordlaka)
 *
 * ZMIANA WOBEC POPRZEDNIEJ WERSJI: wspólny nagłówek zniknął ze szkieletu.
 * Każdy ekran ma teraz własny (przez `TabHeading`), bo sekcja 11 chce,
 * żeby nagłówek niósł, GDZIE jesteś - a jeden wspólny mówił na wszystkich
 * pięciu zakładkach to samo.
 *
 * Dolna krawędź NIE jest w `edges`: pasek zakładek sam dolicza margines
 * bezpieczny, więc podwójne liczenie podniosłoby go nad gest home bara.
 */
import * as React from "react";
import { StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "@/theme/theme";
import { MainTabs } from "./MainTabs";

export function MainShell() {
  const { c } = useTheme();
  return (
    <SafeAreaView style={[styles.root, { backgroundColor: c.bg }]} edges={["top"]}>
      <View style={styles.content}>
        <MainTabs />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  content: {
    flex: 1,
    minHeight: 0,
  },
});
