/**
 * Karta "Powiadomienia push" w Ustawieniach - widoczna WYŁĄCZNIE w
 * kompilacji web (ORDLY Mobile jako PWA). Natywne iOS/Android mają dostać
 * to docelowo przez Expo Push (Faza 2, 01_app.md), więc na natywnych
 * platformach ten komponent renderuje `null`.
 */
import * as React from "react";
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, View } from "react-native";

import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { family, radii, spacing, typography } from "@/theme/typography";
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

function isPolishFew(n: number): boolean {
  return n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14);
}

function deviceWord(n: number): string {
  if (n === 1) return "urządzenie";
  return isPolishFew(n) ? "urządzenia" : "urządzeń";
}

function expiredWord(n: number): string {
  if (n === 1) return "wygasłą subskrypcję";
  return isPolishFew(n) ? "wygasłe subskrypcje" : "wygasłych subskrypcji";
}

export function PushNotificationsCard() {
  const styles = useThemedStyles(createStyles);
  const { c } = useTheme();
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
      if (cancelled) return;
      setSubscribed(Boolean(sub));
      // Telefon może mieć subskrypcję, o której Pi już nie wie (np. usuniętą
      // jako wygasłą albo po odtworzeniu bazy) - wtedy status mówi
      // "Włączone", a powiadomienia nie przychodzą. Zapis jest idempotentny,
      // więc odświeżamy go przy każdym wejściu w Ustawienia.
      const json = sub?.toJSON() as RawPushSubscriptionJson | undefined;
      if (json?.endpoint && json.keys?.p256dh && json.keys.auth) {
        subscribeMutation.mutate({
          endpoint: json.endpoint,
          keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
        });
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
      const expired = result.expired ?? 0;
      setTestResult(
        `Wysłano na ${result.sent_to} ${deviceWord(result.sent_to)}.` +
          (expired > 0
            ? ` Usunięto ${expired} ${expiredWord(expired)} (np. ze starego telefonu).`
            : "")
      );
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
          <ActivityIndicator color={c.acc} />
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
                <ActivityIndicator color={subscribed ? c.tx : c.onAcc} />
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

const createStyles = (c: Palette) =>
  StyleSheet.create({
  sectionTitle: {
    ...typography.sectionTitle,
    color: c.tx,
    marginBottom: spacing.sm,
  },
  card: {
    backgroundColor: c.card,
    borderWidth: 1,
    borderColor: c.line,
    borderRadius: radii.lg,
    padding: spacing.lg,
    marginBottom: spacing.lg,
  },
  info: {
    ...typography.footnote,
    color: c.tx2,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: spacing.md,
  },
  rowLabel: {
    ...typography.footnote,
    color: c.tx2,
  },
  rowValue: {
    ...typography.calloutSemibold,
    color: c.tx,
  },
  button: {
    height: 48,
    backgroundColor: c.acc,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonGhost: {
    backgroundColor: c.card2,
    borderWidth: 1,
    borderColor: c.line,
  },
  buttonLabel: {
    fontSize: 15,
    fontFamily: family.sansSemibold,
    color: c.onAcc,
  },
  buttonGhostLabel: {
    fontSize: 15,
    fontFamily: family.sansSemibold,
    color: c.tx,
  },
  success: {
    ...typography.caption,
    color: c.acc,
    marginTop: spacing.sm,
  },
  error: {
    ...typography.caption,
    color: c.coral,
    marginTop: spacing.sm,
  },
});
