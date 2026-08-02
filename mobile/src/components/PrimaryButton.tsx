/**
 * Główny przycisk akcji - gradient primary -> accent z poświatą (§15.5:
 * maks. 1 gradient dekoracyjny na ekran, wyłącznie primary -> accent).
 */
import * as React from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, type ViewStyle } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { colors } from "@/theme/colors";
import { radii, typography } from "@/theme/typography";

interface PrimaryButtonProps {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  loading?: boolean;
  icon?: React.ReactNode;
  style?: ViewStyle;
}

export function PrimaryButton({
  label,
  onPress,
  disabled,
  loading,
  icon,
  style,
}: PrimaryButtonProps) {
  const isDisabled = disabled || loading;
  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      style={({ pressed }) => [
        styles.wrap,
        style,
        isDisabled && styles.disabled,
        pressed && !isDisabled && styles.pressed,
      ]}
    >
      <LinearGradient
        colors={[colors.primary, colors.accent]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.gradient}
      >
        {loading ? (
          <ActivityIndicator color={colors.onPrimary} />
        ) : (
          <>
            {icon}
            <Text style={styles.label}>{label}</Text>
          </>
        )}
      </LinearGradient>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: {
    height: 52,
    borderRadius: radii.lg,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.35,
    shadowRadius: 18,
    elevation: 6,
  },
  gradient: {
    flex: 1,
    borderRadius: radii.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  label: {
    ...typography.buttonLabel,
    fontSize: 15,
    color: colors.onPrimary,
  },
  pressed: {
    opacity: 0.92,
    transform: [{ scale: 0.99 }],
  },
  disabled: {
    opacity: 0.45,
  },
});
