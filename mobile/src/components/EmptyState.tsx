/**
 * Stan pusty — ikona w okręgu na tle surface (albo maskotka dla "brak
 * zamówień w ogóle", §15.16), tytuł + jedno zdanie instrukcji, opcjonalna
 * akcja (CTA ghost). Każdy ekran ma zdefiniowany stan pusty (kryterium
 * akceptacji nr 1).
 */
import * as React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { Palette } from "@/theme/colors";
import { useThemedStyles } from "@/theme/theme";
import { radii, spacing, typography } from "@/theme/typography";
import { Ordlak, type OrdlakState } from "./Ordlak";

interface EmptyStateProps {
  icon?: React.ReactNode;
  /**
   * Stan maskotki. Pusty stan listy to jedno z miejsc, gdzie Ordlak
   * SPI (sekcja 6) - "brak zwrotow" nie jest awaria i nie ma po co
   * swiecic. Pominiete = brak maskotki (tylko ikona, jesli podana).
   */
  mascotPose?: OrdlakState;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({
  icon,
  mascotPose,
  title,
  description,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  const styles = useThemedStyles(createStyles);
  return (
    <View style={styles.container}>
      {mascotPose ? (
        <Ordlak state={mascotPose} size={76} style={styles.mascot} />
      ) : icon ? (
        <View style={styles.iconWrap}>{icon}</View>
      ) : null}
      <Text style={styles.title}>{title}</Text>
      {description ? <Text style={styles.description}>{description}</Text> : null}
      {actionLabel && onAction ? (
        <Pressable
          onPress={onAction}
          style={({ pressed }) => [styles.action, pressed && { opacity: 0.8 }]}
        >
          <Text style={styles.actionLabel}>{actionLabel}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const createStyles = (c: Palette) =>
  StyleSheet.create({
  container: {
    alignItems: "center",
    paddingVertical: spacing.xxl,
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
  },
  iconWrap: {
    width: 56,
    height: 56,
    borderRadius: radii.full,
    backgroundColor: c.card,
    borderWidth: 1,
    borderColor: c.line,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.xs,
  },
  mascot: {
    marginBottom: spacing.xs,
  },
  title: {
    ...typography.calloutSemibold,
    color: c.tx,
    textAlign: "center",
  },
  description: {
    ...typography.footnote,
    color: c.tx2,
    textAlign: "center",
  },
  action: {
    marginTop: spacing.sm,
    height: 40,
    paddingHorizontal: spacing.lg,
    borderRadius: radii.full,
    borderWidth: 1,
    borderColor: c.line2,
    alignItems: "center",
    justifyContent: "center",
  },
  actionLabel: {
    ...typography.caption,
    fontSize: 13,
    color: c.acc,
  },
});
