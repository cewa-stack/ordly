/**
 * Komunikat błędu + przycisk ponowienia (ghost z borderem primary).
 * Każdy ekran ma zdefiniowany stan błędu (kryterium akceptacji nr 1).
 */
import * as React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({
  message = "Nie udało się pobrać danych",
  onRetry,
}: ErrorStateProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.message}>{message}</Text>
      {onRetry ? (
        <Pressable
          onPress={onRetry}
          style={({ pressed }) => [styles.button, pressed && { opacity: 0.8 }]}
          hitSlop={8}
        >
          <Text style={styles.buttonLabel}>Spróbuj ponownie</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    paddingVertical: spacing.xl,
    gap: spacing.md,
  },
  message: {
    ...typography.footnote,
    color: colors.textSecondary,
    textAlign: "center",
  },
  button: {
    height: 40,
    paddingHorizontal: spacing.lg,
    borderRadius: radii.full,
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonLabel: {
    ...typography.caption,
    fontSize: 13,
    color: colors.primary,
  },
});
