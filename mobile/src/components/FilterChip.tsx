/**
 * Chip filtra — §15.9: wys. 32 pt, radius pełny. Aktywny: tło primary 12%,
 * tekst primary, border primary 40%. Nieaktywny: tło surface, tekst
 * textSecondary.
 */
import * as React from "react";
import { Pressable, StyleSheet, Text } from "react-native";

import type { Palette } from "@/theme/colors";
import { useThemedStyles } from "@/theme/theme";
import { family, radii } from "@/theme/typography";

interface FilterChipProps {
  label: string;
  active?: boolean;
  onPress?: () => void;
}

export function FilterChip({ label, active, onPress }: FilterChipProps) {
  const styles = useThemedStyles(createStyles);
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        active && styles.chipActive,
        pressed && styles.pressed,
      ]}
      hitSlop={4}
    >
      <Text style={[styles.label, active && styles.labelActive]}>{label}</Text>
    </Pressable>
  );
}

const createStyles = (c: Palette) =>
  StyleSheet.create({
  chip: {
    height: 32,
    justifyContent: "center",
    paddingHorizontal: 14,
    borderRadius: radii.full,
    backgroundColor: c.card,
    borderWidth: 1,
    borderColor: c.line,
  },
  chipActive: {
    backgroundColor: c.accDim,
    borderColor: c.line2,
  },
  pressed: {
    opacity: 0.8,
  },
  label: {
    fontSize: 14,
    fontFamily: family.sansMedium,
    color: c.tx2,
  },
  labelActive: {
    color: c.acc,
    fontFamily: family.sansSemibold,
  },
});
