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

import { withAlpha } from "@/theme/colors";
import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { family, radii, spacing, typography } from "@/theme/typography";

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
  const styles = useThemedStyles(createStyles);
  const { c } = useTheme();
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
                { color: destructive ? c.coral : c.onAcc },
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

const createStyles = (c: Palette) =>
  StyleSheet.create({
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
    backgroundColor: c.card,
    borderWidth: 1,
    borderColor: c.line,
    borderRadius: radii.sheet,
    padding: spacing.xl,
  },
  title: {
    ...typography.title2,
    fontSize: 19,
    lineHeight: 25,
    color: c.tx,
  },
  description: {
    ...typography.footnote,
    color: c.tx2,
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
    backgroundColor: c.acc,
  },
  confirmDestructive: {
    backgroundColor: withAlpha(c.coral, 0.14),
  },
  confirmLabel: {
    fontSize: 15,
    fontFamily: family.sansSemibold,
  },
  cancel: {
    height: 44,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.xs,
  },
  cancelLabel: {
    fontSize: 15,
    fontFamily: family.sansMedium,
    color: c.tx2,
  },
  pressed: {
    opacity: 0.8,
  },
  disabled: {
    opacity: 0.5,
  },
});
