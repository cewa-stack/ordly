/**
 * Ustawienia - adres API, token (zamaskowany), wylogowanie, ostatnie
 * zdarzenia systemowe (odpowiednik /logs).
 *
 * Wylogowanie przez ConfirmDialog (nie Alert.alert) — Alert z przyciskami
 * jest no-opem w react-native-web, więc na PWA przycisk byłby "widmem".
 */
import * as React from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Switch, Text, View } from "react-native";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { useAuth } from "@/store/auth";
import { useLogs } from "@/api/hooks";
import type { EventLog } from "@/api/types";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PushNotificationsCard } from "@/components/PushNotificationsCard";
import { Skeleton } from "@/components/Skeleton";
import { FaceIdIcon } from "@/icons";
import { formatDate } from "@/utils/format";

function maskToken(): string {
  return "••••••••••••";
}

const LEVEL_COLOR: Record<string, string> = {
  INFO: colors.textSecondary,
  WARNING: colors.warning,
  ERROR: colors.danger,
  CRITICAL: colors.danger,
};

export function SettingsScreen() {
  const {
    baseUrl,
    username,
    logout,
    biometricAvailable,
    biometricEnabled,
    biometricLabel,
    confirmBiometricEnroll,
    disableBiometric,
  } = useAuth();
  const logs = useLogs();
  const [logoutDialogOpen, setLogoutDialogOpen] = React.useState(false);
  const [loggingOut, setLoggingOut] = React.useState(false);
  const [biometricBusy, setBiometricBusy] = React.useState(false);
  const [biometricError, setBiometricError] = React.useState(false);

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      setLoggingOut(false);
      setLogoutDialogOpen(false);
    }
  }

  async function handleBiometricToggle(next: boolean) {
    setBiometricError(false);
    setBiometricBusy(true);
    try {
      if (next) {
        const ok = await confirmBiometricEnroll();
        setBiometricError(!ok);
      } else {
        await disableBiometric();
      }
    } finally {
      setBiometricBusy(false);
    }
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.sectionTitle}>Połączenie</Text>
      <View style={styles.card}>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Adres API</Text>
          <Text style={styles.rowValueMono} numberOfLines={1}>
            {baseUrl}
          </Text>
        </View>
        <View style={[styles.row, styles.rowBorder]}>
          <Text style={styles.rowLabel}>Login</Text>
          <Text style={styles.rowValueMono}>{username ?? "—"}</Text>
        </View>
        <View style={[styles.row, styles.rowBorder]}>
          <Text style={styles.rowLabel}>Token</Text>
          <Text style={styles.rowValueMono}>{maskToken()}</Text>
        </View>
      </View>

      {biometricAvailable ? (
        <>
          <Text style={styles.sectionTitle}>Bezpieczeństwo</Text>
          <View style={styles.card}>
            <View style={styles.row}>
              <View style={styles.bioIconWrap}>
                <FaceIdIcon size={16} color={colors.primary} />
              </View>
              <View style={styles.grow}>
                <Text style={styles.rowTitle}>{biometricLabel}</Text>
                <Text style={styles.rowSub}>Szybkie odblokowanie zamiast hasła</Text>
              </View>
              {biometricBusy ? (
                <ActivityIndicator color={colors.primary} />
              ) : (
                <Switch
                  value={biometricEnabled}
                  onValueChange={(next) => void handleBiometricToggle(next)}
                  trackColor={{ false: colors.border, true: colors.primary }}
                  thumbColor={colors.text}
                />
              )}
            </View>
            {biometricError ? (
              <Text style={styles.bioError}>
                Nie udało się włączyć {biometricLabel} — spróbuj ponownie.
              </Text>
            ) : null}
          </View>
        </>
      ) : null}

      <PushNotificationsCard />

      <Text style={styles.sectionTitle}>Ostatnie zdarzenia</Text>
      <View style={[styles.card, styles.cardPadded]}>
        {logs.isPending ? (
          <Skeleton height={80} />
        ) : logs.isError ? (
          <ErrorState onRetry={() => logs.refetch()} />
        ) : (logs.data ?? []).length === 0 ? (
          <EmptyState title="Brak zarejestrowanych zdarzeń" />
        ) : (
          (logs.data ?? []).slice(0, 30).map((entry: EventLog, index: number) => (
            <View
              key={`${entry.created_at}-${index}`}
              style={[styles.logRow, index > 0 && styles.rowBorder]}
            >
              <View style={styles.logMain}>
                <View
                  style={[
                    styles.logDot,
                    { backgroundColor: LEVEL_COLOR[entry.level] ?? colors.textSecondary },
                  ]}
                />
                <Text style={styles.logLabel} numberOfLines={1}>
                  {entry.event_type}
                </Text>
              </View>
              <Text style={styles.logDate}>{formatDate(entry.created_at)}</Text>
            </View>
          ))
        )}
      </View>

      <Pressable
        style={({ pressed }) => [styles.logoutButton, pressed && { opacity: 0.85 }]}
        onPress={() => setLogoutDialogOpen(true)}
      >
        <Text style={styles.logoutLabel}>Wyloguj się</Text>
      </Pressable>

      <ConfirmDialog
        visible={logoutDialogOpen}
        title="Wylogować z ORDLY?"
        description="Adres API i token zostaną usunięte z tego urządzenia. Będzie trzeba je wkleić ponownie."
        confirmLabel="Wyloguj"
        destructive
        busy={loggingOut}
        onConfirm={() => void handleLogout()}
        onCancel={() => setLogoutDialogOpen(false)}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.xl,
    paddingBottom: 60,
  },
  sectionTitle: {
    ...typography.sectionTitle,
    color: colors.text,
    marginBottom: spacing.md,
  },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.xl,
  },
  cardPadded: {
    paddingVertical: spacing.xs,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: spacing.lg,
  },
  rowBorder: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  rowLabel: {
    ...typography.footnote,
    color: colors.textSecondary,
  },
  rowValueMono: {
    ...typography.mono,
    color: colors.text,
    flexShrink: 1,
    textAlign: "right",
  },
  grow: {
    flex: 1,
    minWidth: 0,
  },
  bioIconWrap: {
    width: 32,
    height: 32,
    borderRadius: radii.full,
    backgroundColor: colors.primaryTint,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.sm,
  },
  rowTitle: {
    ...typography.calloutSemibold,
    fontSize: 14,
    color: colors.text,
  },
  rowSub: {
    ...typography.caption,
    fontSize: 11.5,
    color: colors.textSecondary,
    marginTop: 1,
  },
  bioError: {
    ...typography.caption,
    color: colors.danger,
    paddingBottom: spacing.md,
  },
  logRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: spacing.md,
  },
  logMain: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    flexShrink: 1,
  },
  logDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  logLabel: {
    ...typography.footnote,
    color: colors.text,
    flexShrink: 1,
  },
  logDate: {
    ...typography.caption,
    fontSize: 11,
    color: colors.textDim,
  },
  logoutButton: {
    height: 52,
    backgroundColor: colors.dangerTint,
    borderRadius: radii.lg,
    alignItems: "center",
    justifyContent: "center",
  },
  logoutLabel: {
    fontSize: 15,
    fontWeight: "600",
    color: colors.danger,
  },
});
