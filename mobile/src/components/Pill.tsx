/**
 * Pastylka statusowa z jawnym kolorem/tłem - ten sam wygląd co StatusBadge
 * (wys. 24, radius pełny, tekst 11 SemiBold), ale dla statusów spoza
 * orderStatusColor (np. dyskusje/reklamacje), gdzie kolor zależy od mapy
 * właściwej dla danego ekranu, nie od etykiety zamówienia.
 */
import * as React from "react";
import { StyleSheet, Text, View } from "react-native";

import { radii, typography } from "@/theme/typography";

interface PillProps {
  label: string;
  color: string;
  tint: string;
}

export function Pill({ label, color, tint }: PillProps) {
  return (
    <View style={[styles.badge, { backgroundColor: tint }]}>
      <Text style={[styles.label, { color }]} numberOfLines={1}>
        {label}
      </Text>
    </View>
  );
}

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
