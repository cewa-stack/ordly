/**
 * Pasek „brak połączenia z Pi” nad zakładkami.
 *
 * Pokazuje się tylko wtedy, gdy Pi nie odpowiada (błąd SIECI, nie błąd
 * serwera), a mimo to mamy co pokazać - ostatni stan z `offlineCache`.
 * Mówi, z której godziny są dane, bo „2 do spakowania” sprzed doby to
 * inna informacja niż sprzed minuty. Dotknięcie próbuje połączyć się
 * jeszcze raz.
 */
import * as React from "react";
import { Pressable, StyleSheet, Text } from "react-native";
import { useQueryClient } from "@tanstack/react-query";

import type { Palette } from "@/theme/colors";
import { withAlpha } from "@/theme/colors";
import { useThemedStyles } from "@/theme/theme";
import { fonts, spacing } from "@/theme/typography";
import { useDashboard } from "@/api/hooks";
import { ApiError } from "@/api/client";

function stamp(ms: number): string {
  const date = new Date(ms);
  const time = date.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
  const today = new Date();
  if (date.toDateString() === today.toDateString()) return time;
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) return `wczoraj ${time}`;
  return `${date.toLocaleDateString("pl-PL", { day: "numeric", month: "short" })} ${time}`;
}

export function OfflineBanner() {
  const styles = useThemedStyles(createStyles);
  const queryClient = useQueryClient();
  const dashboard = useDashboard();

  const offline =
    dashboard.isError &&
    dashboard.error instanceof ApiError &&
    dashboard.error.status === 0 &&
    dashboard.data !== undefined;
  if (!offline) return null;

  return (
    <Pressable
      onPress={() => void queryClient.refetchQueries({ type: "active" })}
      disabled={dashboard.isFetching}
      accessibilityRole="button"
      accessibilityLabel="Brak połączenia z Pi. Dotknij, żeby spróbować ponownie."
      style={({ pressed }) => [styles.bar, pressed && { opacity: 0.8 }]}
    >
      <Text style={styles.text} numberOfLines={1}>
        {dashboard.isFetching
          ? "Łączę z Pi…"
          : `Brak połączenia z Pi · stan z ${stamp(dashboard.dataUpdatedAt)} · dotknij, by spróbować`}
      </Text>
    </Pressable>
  );
}

const createStyles = (c: Palette) =>
  StyleSheet.create({
    bar: {
      marginHorizontal: spacing.xl,
      marginTop: spacing.xs,
      marginBottom: spacing.xs,
      paddingVertical: 7,
      paddingHorizontal: 12,
      borderRadius: 10,
      backgroundColor: withAlpha(c.amber, 0.14),
    },
    text: {
      ...fonts.mono,
      fontSize: 10.5,
      color: c.amber,
      textAlign: "center",
    },
  });
