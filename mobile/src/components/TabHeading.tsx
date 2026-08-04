/**
 * Nagłówek zakładki wg sekcji 6.2 specyfikacji: tytuł po lewej,
 * licznik po prawej (`.ph` w koncepcji).
 *
 * Zastępuje dawne "large title" z osobnym przyciskiem synchronizacji -
 * synchronizacja przeniosła się do wspólnego nagłówka aplikacji, bo
 * sekcja 6.1 mówi wprost, że to JEDYNE działanie w całej aplikacji
 * mobilnej i ma być jedno, nie pięć kopii na pięciu ekranach.
 */
import * as React from "react";
import { StyleSheet, Text, View } from "react-native";

import { colors } from "@/theme/colors";
import { spacing, typography } from "@/theme/typography";

interface TabHeadingProps {
  title: string;
  /** Krótka informacja o zawartości, np. "12 pozycji" albo "3 czekają". */
  count?: string;
}

export function TabHeading({ title, count }: TabHeadingProps) {
  return (
    <View style={styles.row}>
      <Text style={styles.title}>{title}</Text>
      {count ? <Text style={styles.count}>{count}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg + 6,
    paddingTop: 6,
    paddingBottom: 11,
  },
  title: {
    ...typography.tabHeading,
    color: colors.text,
    letterSpacing: -0.23,
  },
  count: {
    ...typography.meta,
    fontSize: 10.5,
    color: "#6E7C77",
  },
});
