/**
 * Szkielet aplikacji mobilnej wg sekcji 6.1 specyfikacji:
 *
 *   pasek stanu systemu
 *   powitanie + Ordi (46 px)
 *   pigułka synchronizacji     <- jedyne działanie w aplikacji
 *   -------------------------
 *   zawartość zakładki
 *   -------------------------
 *   pasek zakładek (pływający)
 *
 * Nagłówek stoi NAD nawigatorem zakładek, nie w środku - dzięki temu nie
 * przewija się razem z listą i nie trzeba go powtarzać w każdym z pięciu
 * ekranów.
 */
import * as React from "react";
import { StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { colors } from "@/theme/colors";
import { AppHeader } from "@/components/AppHeader";
import { useAuth } from "@/store/auth";
import { MainTabs } from "./MainTabs";

export function MainShell() {
  const { username } = useAuth();

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <AppHeader username={username ?? "sprzedawco"} />
      <View style={styles.content}>
        <MainTabs />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    flex: 1,
    minHeight: 0,
  },
});
