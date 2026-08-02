/**
 * Stan pusty — ikona w okręgu na tle surface (albo maskotka dla "brak
 * zamówień w ogóle", §15.16), tytuł + jedno zdanie instrukcji, opcjonalna
 * akcja (CTA ghost). Każdy ekran ma zdefiniowany stan pusty (kryterium
 * akceptacji nr 1).
 */
import * as React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { Mascot, type MascotPose } from "./Mascot";

interface EmptyStateProps {
  icon?: React.ReactNode;
  /** Poza maskotki - patrz Mascot.tsx. Pominięte = brak maskotki (tylko icon, jeśli podany). */
  mascotPose?: MascotPose;
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
  return (
    <View style={styles.container}>
      {mascotPose ? (
        <Mascot pose={mascotPose} size={76} floaty={false} style={styles.mascot} />
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

const styles = StyleSheet.create({
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
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.xs,
  },
  mascot: {
    marginBottom: spacing.xs,
  },
  title: {
    ...typography.calloutSemibold,
    color: colors.text,
    textAlign: "center",
  },
  description: {
    ...typography.footnote,
    color: colors.textSecondary,
    textAlign: "center",
  },
  action: {
    marginTop: spacing.sm,
    height: 40,
    paddingHorizontal: spacing.lg,
    borderRadius: radii.full,
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    alignItems: "center",
    justifyContent: "center",
  },
  actionLabel: {
    ...typography.caption,
    fontSize: 13,
    color: colors.primary,
  },
});
