/**
 * Pastylka statusu zamowienia. Mowi tym samym jezykiem co desktop
 * (sekcja 7): `hot` wymaga dzialania, `go` jest w toku, `mute` jest
 * zamkniete. "Wyslane" i "Odebrane" sa `mute`, nie `go` - swiecenie
 * rzeczy juz skonczonych to glowny powod, przez ktory interfejsy robia
 * sie hałaśliwe.
 */
import * as React from "react";
import { StyleSheet, Text, View } from "react-native";

import { ORDER_TONE, toneStyle } from "@/theme/colors";
import { useTheme } from "@/theme/theme";
import { radii, typography } from "@/theme/typography";

interface StatusBadgeProps {
  label: string;
}

export function StatusBadge({ label }: StatusBadgeProps) {
  const { c } = useTheme();
  const { background, text } = toneStyle(ORDER_TONE[label] ?? "mute", c);
  return (
    <View style={[styles.badge, { backgroundColor: background }]}>
      <Text style={[styles.label, { color: text }]}>{label}</Text>
    </View>
  );
}

// Sam ksztalt nie zalezy od atmosfery, wiec arkusz zostaje stala.
const styles = StyleSheet.create({
  badge: {
    height: 24,
    borderRadius: radii.full,
    paddingHorizontal: 10,
    alignItems: "center",
    justifyContent: "center",
    alignSelf: "flex-start",
  },
  label: {
    ...typography.badgeLabel,
  },
});
