/**
 * Ustawienia - adres API, token (zamaskowany), wylogowanie, ostatnie
 * zdarzenia systemowe (odpowiednik /logs).
 *
 * Wylogowanie przez ConfirmDialog (nie Alert.alert) — Alert z przyciskami
 * jest no-opem w react-native-web, więc na PWA przycisk byłby "widmem".
 */
import * as React from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Switch, Text, View } from "react-native";

import { withAlpha } from "@/theme/colors";
import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { family, fonts, radii, spacing, typography } from "@/theme/typography";
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

/** Kolor poziomu zdarzenia w AKTYWNEJ atmosferze. */
function levelColor(level: string, c: Palette): string {
  if (level === "WARNING") return c.amber;
  if (level === "ERROR" || level === "CRITICAL") return c.coral;
  return c.tx2;
}

/**
 * Zdarzenia po polsku - lista pokazywała surowe `OrderCreated`
 * i `SyncFinished`. Nieznany typ zostaje surowy, zamiast zgadywać.
 */
const EVENT_LABEL: Record<string, string> = {
  OrderCreated: "Nowe zamówienie",
  OrderCancelled: "Anulowane zamówienie",
  OrderPackingStarted: "Rozpoczęto pakowanie",
  OrderReturnCreated: "Nowy zwrot",
  AllegroLokalnieEventDetected: "Mail z Allegro Lokalnie",
  OlxEventDetected: "Mail z OLX",
  DisputeNoticeDetected: "Nowa dyskusja",
  SyncStarted: "Start synchronizacji",
  SyncFinished: "Koniec synchronizacji",
};

export function SettingsScreen() {
  const styles = useThemedStyles(createStyles);
  const { c, mode, preference, setPreference } = useTheme();
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
                <FaceIdIcon size={16} color={c.acc} />
              </View>
              <View style={styles.grow}>
                <Text style={styles.rowTitle}>{biometricLabel}</Text>
                <Text style={styles.rowSub}>Szybkie odblokowanie zamiast hasła</Text>
              </View>
              {biometricBusy ? (
                <ActivityIndicator color={c.acc} />
              ) : (
                <Switch
                  value={biometricEnabled}
                  onValueChange={(next) => void handleBiometricToggle(next)}
                  trackColor={{ false: c.line, true: c.acc }}
                  thumbColor={c.tx}
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

      {/*
        Przelaczanie atmosfery (sekcja 11): GODZINA plus reczne
        nadpisanie. Czujnik jasnosci jest kuszacy, ale skacze przy kazdym
        przejsciu pod lampa - dlatego go tu nie ma.
      */}
      <Text style={styles.sectionTitle}>Atmosfera</Text>
      <View style={styles.card}>
        <View style={styles.themeRow}>
          {(
            [
              { key: "auto", label: "Automatycznie" },
              { key: "day", label: "Dzień" },
              { key: "night", label: "Noc" },
            ] as const
          ).map((option) => {
            const active = preference === option.key;
            return (
              <Pressable
                key={option.key}
                onPress={() => setPreference(option.key)}
                accessibilityRole="radio"
                accessibilityState={{ selected: active }}
                style={[
                  styles.themeOption,
                  active && { backgroundColor: c.accDim, borderColor: "transparent" },
                ]}
              >
                <Text style={[styles.themeLabel, active && { color: c.acc }]}>
                  {option.label}
                </Text>
              </Pressable>
            );
          })}
        </View>
        <Text style={styles.themeHint}>
          {preference === "auto"
            ? `Dzień od 6:00 do 20:00. Teraz świeci ${mode === "day" ? "dzienna" : "nocna"}.`
            : "Ustawienie ręczne - godzina nie będzie jej zmieniać."}
        </Text>
      </View>

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
                    { backgroundColor: levelColor(entry.level, c) },
                  ]}
                />
                <Text style={styles.logLabel} numberOfLines={1}>
                  {EVENT_LABEL[entry.event_type] ?? entry.event_type}
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

const createStyles = (c: Palette) =>
  StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: c.bg,
  },
  content: {
    padding: spacing.xl,
    paddingBottom: 60,
  },
  themeRow: {
    flexDirection: "row",
    gap: 8,
    padding: 12,
  },
  themeOption: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 9,
    borderRadius: radii.full,
    borderWidth: 1,
    borderColor: c.line2,
  },
  themeLabel: {
    ...fonts.status,
    fontSize: 11.5,
    color: c.tx2,
  },
  themeHint: {
    ...fonts.caption,
    color: c.tx3,
    paddingHorizontal: 12,
    paddingBottom: 12,
  },
  sectionTitle: {
    ...typography.sectionTitle,
    color: c.tx,
    marginBottom: spacing.md,
  },
  card: {
    backgroundColor: c.card,
    borderWidth: 1,
    borderColor: c.line,
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
    borderTopColor: c.line,
  },
  rowLabel: {
    ...typography.footnote,
    color: c.tx2,
  },
  rowValueMono: {
    ...typography.mono,
    color: c.tx,
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
    backgroundColor: c.accDim,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.sm,
  },
  rowTitle: {
    ...typography.calloutSemibold,
    fontSize: 14,
    color: c.tx,
  },
  rowSub: {
    ...typography.caption,
    fontSize: 11.5,
    color: c.tx2,
    marginTop: 1,
  },
  bioError: {
    ...typography.caption,
    color: c.coral,
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
    color: c.tx,
    flexShrink: 1,
  },
  logDate: {
    ...typography.caption,
    fontSize: 11,
    color: c.tx3,
  },
  logoutButton: {
    height: 52,
    backgroundColor: withAlpha(c.coral, 0.14),
    borderRadius: radii.lg,
    alignItems: "center",
    justifyContent: "center",
  },
  logoutLabel: {
    fontSize: 15,
    fontFamily: family.sansSemibold,
    color: c.coral,
  },
});
