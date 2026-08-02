/**
 * Dialog potwierdzenia — §15.12: wyłącznie decyzje nieodwracalne
 * (wylogowanie, usunięcie). Karta wycentrowana 320 pt, radius 24,
 * przyciski pionowo: destrukcyjny na górze, "Anuluj" ghost pod spodem.
 *
 * Własny komponent zamiast `Alert.alert`, bo na webie (PWA) Alert.alert
 * z przyciskami jest no-opem w react-native-web — przycisk "Wyloguj"
 * wyglądałby na działający, a nie robiłby nic. Ten dialog działa
 * identycznie na iOS / Android / web.
 */
import * as React from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";

interface ConfirmDialogProps {
  visible: boolean;
  title: string;
  description?: string;
  confirmLabel: string;
  /** Destrukcyjne akcje dostają tło danger 12% + tekst danger (§15.5). */
  destructive?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  visible,
  title,
  description,
  confirmLabel,
  destructive,
  busy,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={styles.scrim}>
        <View style={styles.card}>
          <Text style={styles.title}>{title}</Text>
          {description ? <Text style={styles.description}>{description}</Text> : null}
          <Pressable
            onPress={onConfirm}
            disabled={busy}
            style={({ pressed }) => [
              styles.confirm,
              destructive ? styles.confirmDestructive : styles.confirmPrimary,
              pressed && styles.pressed,
              busy && styles.disabled,
            ]}
          >
            <Text
              style={[
                styles.confirmLabel,
                { color: destructive ? colors.danger : colors.onPrimary },
              ]}
            >
              {busy ? "Chwila…" : confirmLabel}
            </Text>
          </Pressable>
          <Pressable
            onPress={onCancel}
            disabled={busy}
            style={({ pressed }) => [styles.cancel, pressed && styles.pressed]}
          >
            <Text style={styles.cancelLabel}>Anuluj</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.6)",
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.xl,
  },
  card: {
    width: "100%",
    maxWidth: 320,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sheet,
    padding: spacing.xl,
  },
  title: {
    ...typography.title2,
    fontSize: 19,
    lineHeight: 25,
    color: colors.text,
  },
  description: {
    ...typography.footnote,
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
  confirm: {
    height: 48,
    borderRadius: radii.lg,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.xl,
  },
  confirmPrimary: {
    backgroundColor: colors.primary,
  },
  confirmDestructive: {
    backgroundColor: colors.dangerTint,
  },
  confirmLabel: {
    fontSize: 15,
    fontWeight: "600",
  },
  cancel: {
    height: 44,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.xs,
  },
  cancelLabel: {
    fontSize: 15,
    fontWeight: "500",
    color: colors.textSecondary,
  },
  pressed: {
    opacity: 0.8,
  },
  disabled: {
    opacity: 0.5,
  },
});
