/**
 * Chip filtra — §15.9: wys. 32 pt, radius pełny. Aktywny: tło primary 12%,
 * tekst primary, border primary 40%. Nieaktywny: tło surface, tekst
 * textSecondary.
 */
import * as React from "react";
import { Pressable, StyleSheet, Text } from "react-native";

import { colors } from "@/theme/colors";
import { radii } from "@/theme/typography";

interface FilterChipProps {
  label: string;
  active?: boolean;
  onPress?: () => void;
}

export function FilterChip({ label, active, onPress }: FilterChipProps) {
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

const styles = StyleSheet.create({
  chip: {
    height: 32,
    justifyContent: "center",
    paddingHorizontal: 14,
    borderRadius: radii.full,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: {
    backgroundColor: colors.primaryTint,
    borderColor: colors.primaryBorder,
  },
  pressed: {
    opacity: 0.8,
  },
  label: {
    fontSize: 14,
    fontWeight: "500",
    color: colors.textSecondary,
  },
  labelActive: {
    color: colors.primary,
    fontWeight: "600",
  },
});
