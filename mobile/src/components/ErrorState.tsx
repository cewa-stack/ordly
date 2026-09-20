/**
 * Komunikat błędu + przycisk ponowienia (ghost z borderem primary).
 * Każdy ekran ma zdefiniowany stan błędu (kryterium akceptacji nr 1).
 */
import * as React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { Palette } from "@/theme/colors";
import { useThemedStyles } from "@/theme/theme";
import { radii, spacing, typography } from "@/theme/typography";

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({
  message = "Nie udało się pobrać danych",
  onRetry,
}: ErrorStateProps) {
  const styles = useThemedStyles(createStyles);
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

const createStyles = (c: Palette) =>
  StyleSheet.create({
  container: {
    alignItems: "center",
    paddingVertical: spacing.xl,
    gap: spacing.md,
  },
  message: {
    ...typography.footnote,
    color: c.tx2,
    textAlign: "center",
  },
  button: {
    height: 40,
    paddingHorizontal: spacing.lg,
    borderRadius: radii.full,
    borderWidth: 1,
    borderColor: c.line2,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonLabel: {
    ...typography.caption,
    fontSize: 13,
    color: c.acc,
  },
});
