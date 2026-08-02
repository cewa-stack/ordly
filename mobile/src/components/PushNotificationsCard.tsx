/**
 * Karta "Powiadomienia push" w Ustawieniach - widoczna WYŁĄCZNIE w
 * kompilacji web (ORDLY Mobile jako PWA). Natywne iOS/Android mają dostać
 * to docelowo przez Expo Push (Faza 2, 01_app.md), więc na natywnych
 * platformach ten komponent renderuje `null`.
 */
import * as React from "react";
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { ApiError } from "@/api/client";
import { useSendTestPush, useSubscribePush, useUnsubscribePush, useVapidStatus } from "@/api/hooks";
import {
  getExistingPushSubscription,
  isWebPushSupported,
  subscribeToPush,
  unsubscribeFromPush,
} from "@/push/webPush";

interface RawPushSubscriptionJson {
  endpoint?: string;
  keys?: { p256dh?: string; auth?: string };
}

export function PushNotificationsCard() {
  const vapid = useVapidStatus();
  const subscribeMutation = useSubscribePush();
  const unsubscribeMutation = useUnsubscribePush();
  const testMutation = useSendTestPush();

  const [subscribed, setSubscribed] = React.useState<boolean | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [testResult, setTestResult] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (Platform.OS !== "web") {
      return;
    }
    let cancelled = false;
    getExistingPushSubscription().then((sub) => {
      if (!cancelled) {
        setSubscribed(Boolean(sub));
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (Platform.OS !== "web") {
    return null;
  }

  async function handleEnable() {
    setError(null);
    setTestResult(null);
    if (!vapid.data?.public_key) {
      return;
    }
    setBusy(true);
    try {
      const subscription = await subscribeToPush(vapid.data.public_key);
      const json = subscription.toJSON() as RawPushSubscriptionJson;
      if (!json.endpoint || !json.keys?.p256dh || !json.keys.auth) {
        throw new Error("Przeglądarka zwróciła niepełną subskrypcję push.");
      }
      await subscribeMutation.mutateAsync({
        endpoint: json.endpoint,
        keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
      });
      setSubscribed(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się włączyć powiadomień.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDisable() {
    setError(null);
    setTestResult(null);
    setBusy(true);
    try {
      const endpoint = await unsubscribeFromPush();
      if (endpoint) {
        await unsubscribeMutation.mutateAsync(endpoint);
      }
      setSubscribed(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się wyłączyć powiadomień.");
    } finally {
      setBusy(false);
    }
  }

  async function handleTest() {
    setError(null);
    setTestResult(null);
    try {
      const result = await testMutation.mutateAsync();
      setTestResult(`Wysłano do ${result.sent_to} urządzeń.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nie udało się wysłać testu.");
    }
  }

  return (
    <>
      <Text style={styles.sectionTitle}>Powiadomienia push</Text>
      <View style={styles.card}>
        {!isWebPushSupported() ? (
          <Text style={styles.info}>
            Ta przeglądarka nie obsługuje powiadomień push. Na iPhonie: dodaj ORDLY Mobile do
            ekranu początkowego (Safari → Udostępnij → Dodaj do ekranu początkowego) i otwórz
            go stamtąd.
          </Text>
        ) : vapid.isPending ? (
          <ActivityIndicator color={colors.primary} />
        ) : !vapid.data?.enabled ? (
          <Text style={styles.info}>
            Backend nie ma jeszcze skonfigurowanego Web Push (brak kluczy VAPID w .env) -
            poproś administratora ORDLY o dokończenie konfiguracji.
          </Text>
        ) : (
          <>
            <View style={styles.row}>
              <Text style={styles.rowLabel}>Status</Text>
              <Text style={styles.rowValue}>
                {subscribed === null ? "Sprawdzanie…" : subscribed ? "Włączone" : "Wyłączone"}
              </Text>
            </View>
            <Pressable
              style={[styles.button, subscribed && styles.buttonGhost]}
              onPress={subscribed ? handleDisable : handleEnable}
              disabled={busy}
            >
              {busy ? (
                <ActivityIndicator color={subscribed ? colors.text : colors.onPrimary} />
              ) : (
                <Text style={subscribed ? styles.buttonGhostLabel : styles.buttonLabel}>
                  {subscribed ? "Wyłącz powiadomienia" : "Włącz powiadomienia"}
                </Text>
              )}
            </Pressable>
            {subscribed ? (
              <Pressable
                style={[styles.button, styles.buttonGhost, { marginTop: spacing.sm }]}
                onPress={handleTest}
                disabled={testMutation.isPending}
              >
                <Text style={styles.buttonGhostLabel}>
                  {testMutation.isPending ? "Wysyłanie…" : "Wyślij testowe powiadomienie"}
                </Text>
              </Pressable>
            ) : null}
            {testResult ? <Text style={styles.success}>{testResult}</Text> : null}
            {error ? <Text style={styles.error}>{error}</Text> : null}
          </>
        )}
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  sectionTitle: {
    ...typography.sectionTitle,
    color: colors.text,
    marginBottom: spacing.sm,
  },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    padding: spacing.lg,
    marginBottom: spacing.lg,
  },
  info: {
    ...typography.footnote,
    color: colors.textSecondary,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: spacing.md,
  },
  rowLabel: {
    ...typography.footnote,
    color: colors.textSecondary,
  },
  rowValue: {
    ...typography.calloutSemibold,
    color: colors.text,
  },
  button: {
    height: 48,
    backgroundColor: colors.primary,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonGhost: {
    backgroundColor: colors.surfaceRaised,
    borderWidth: 1,
    borderColor: colors.border,
  },
  buttonLabel: {
    fontSize: 15,
    fontWeight: "600",
    color: colors.onPrimary,
  },
  buttonGhostLabel: {
    fontSize: 15,
    fontWeight: "600",
    color: colors.text,
  },
  success: {
    ...typography.caption,
    color: colors.success,
    marginTop: spacing.sm,
  },
  error: {
    ...typography.caption,
    color: colors.danger,
    marginTop: spacing.sm,
  },
});
