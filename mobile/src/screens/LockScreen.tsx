/**
 * Ekran blokady - pokazywany przy zimnym starcie, gdy sesja (adres+token)
 * jest już zapisana i użytkownik wcześniej włączył biometrię. Prawdziwy
 * prompt systemowy Face ID/Touch ID/odcisku (patrz utils/biometric.ts) -
 * to jedyna droga wejścia poza wpisaniem hasła jeszcze raz.
 *
 * Górę ekranu zajmuje list przewozowy (`Waybill`) - sklep jest
 * "zapakowany". Etykieta mieszka w elastycznym obszarze NAD treścią,
 * a nie na sztywnych współrzędnych: na niskim telefonie zmniejsza się,
 * zamiast wchodzić pod powitanie.
 *
 * Po udanym Face ID ekran nie znika od razu: taśmy się odklejają,
 * a Ordlak budzi się (mrugnięcie, podskok) i dopiero wtedy
 * `finishUnlock` wpuszcza do aplikacji.
 */
import * as React from "react";
import { Platform, Pressable, StyleSheet, Text, View, type LayoutChangeEvent } from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { family, radii, spacing, typography } from "@/theme/typography";
import { useAuth } from "@/store/auth";
import { Ordlak, type OrdlakState } from "@/components/Ordlak";
import { WAYBILL_ASPECT, Waybill } from "@/components/Waybill";
import { PrimaryButton } from "@/components/PrimaryButton";
import { FaceIdIcon } from "@/icons";

/** Czasy budzenia: oczy się otwierają, potem podskok, potem wejście. */
const WAKE_EYES_MS = 250;
const WAKE_TOTAL_MS = 850;

export function LockScreen() {
  const styles = useThemedStyles(createStyles);
  const { c, mode, reduceMotion } = useTheme();
  const insets = useSafeAreaInsets();
  const { biometricLabel, verifyBiometric, finishUnlock, useFallbackPasswordLogin, username } =
    useAuth();
  const [attempting, setAttempting] = React.useState(false);
  const [failed, setFailed] = React.useState(false);
  const [waking, setWaking] = React.useState<OrdlakState | null>(null);
  const [topArea, setTopArea] = React.useState({ width: 0, height: 0 });
  const attemptedOnMount = React.useRef(false);
  // Blokada drugiego dotknięcia w trakcie budzenia - przycisk nie gaśnie,
  // bo przygaszony wyglądałby jak błąd tuż po udanym Face ID.
  const unlockingRef = React.useRef(false);

  const tryUnlock = React.useCallback(async () => {
    if (unlockingRef.current) return;
    setAttempting(true);
    setFailed(false);
    const ok = await verifyBiometric();
    setAttempting(false);
    if (!ok) {
      setFailed(true);
      return;
    }
    unlockingRef.current = true;
    if (reduceMotion) {
      finishUnlock();
      return;
    }
    setWaking("idle");
    setTimeout(() => setWaking("happy"), WAKE_EYES_MS);
    setTimeout(finishUnlock, WAKE_TOTAL_MS);
  }, [verifyBiometric, finishUnlock, reduceMotion]);

  React.useEffect(() => {
    // Na PWA Safari wpuszcza Face ID (WebAuthn) wyłącznie po dotknięciu.
    // Próba bez gestu kończy się odmową, a ekran od razu wołał „Nie
    // rozpoznano”, zanim ktokolwiek coś zrobił. Natywnie systemowy
    // prompt można podać od razu - tam zostaje automatyczna próba.
    if (attemptedOnMount.current || Platform.OS === "web") {
      return;
    }
    attemptedOnMount.current = true;
    void tryUnlock();
  }, [tryUnlock]);

  const onTopLayout = (event: LayoutChangeEvent) => {
    const { width, height } = event.nativeEvent.layout;
    setTopArea({ width, height });
  };
  // Etykieta nie szersza niż 340 px i zawsze mieszcząca się w pionie.
  const waybillWidth = Math.min(
    340,
    topArea.width - 2 * spacing.xl,
    (topArea.height - spacing.lg) / WAYBILL_ASPECT
  );
  const unlocked = waking !== null;

  const faceLabel = unlocked
    ? "Rozpoznano"
    : attempting
      ? "Sprawdzam…"
      : `Dotknij, aby użyć ${biometricLabel}`;

  return (
    <View style={styles.screen}>
      <StatusBar style={mode === "day" ? "dark" : "light"} />
      <View style={[styles.top, { paddingTop: insets.top + spacing.md }]} onLayout={onTopLayout}>
        {waybillWidth >= 160 ? (
          <Waybill width={waybillWidth} recipient={username} opened={unlocked} />
        ) : null}
      </View>

      <View style={[styles.content, { paddingBottom: insets.bottom + spacing.xxl }]}>
        <Ordlak state={waking ?? "sleep"} size={92} />
        <Text style={styles.greeting}>
          {username ? `Witaj, ${username}` : "Witaj z powrotem"}
        </Text>
        <Text style={styles.subtitle}>Odblokuj ORDLY, żeby wrócić do sklepu.</Text>

        <Pressable
          onPress={() => void tryUnlock()}
          disabled={attempting}
          accessibilityRole="button"
          accessibilityLabel={`Odblokuj przez ${biometricLabel}`}
          style={({ pressed }) => [styles.faceCircle, pressed && { opacity: 0.85 }]}
        >
          <FaceIdIcon size={30} color={c.acc} />
        </Pressable>
        <Text style={[styles.faceLabel, unlocked && { color: c.acc }]}>{faceLabel}</Text>

        {failed ? (
          <Text style={styles.errorText}>
            Nie rozpoznano — spróbuj ponownie albo zaloguj się hasłem.
          </Text>
        ) : null}

        <PrimaryButton
          label={attempting ? "Sprawdzam…" : `Odblokuj przez ${biometricLabel}`}
          onPress={() => void tryUnlock()}
          loading={attempting}
          style={styles.primaryCta}
        />

        <Pressable
          onPress={useFallbackPasswordLogin}
          disabled={unlocked}
          hitSlop={8}
          style={styles.fallback}
        >
          <Text style={styles.fallbackLabel}>Zaloguj się hasłem</Text>
        </Pressable>
      </View>
    </View>
  );
}

const createStyles = (c: Palette) =>
  StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: c.bg,
  },
  top: {
    flex: 1,
    minHeight: 0,
    alignItems: "center",
    justifyContent: "flex-end",
    paddingBottom: spacing.sm,
  },
  content: {
    alignItems: "center",
    paddingHorizontal: spacing.xl,
  },
  greeting: {
    ...typography.title1,
    fontSize: 21,
    color: c.tx,
    marginTop: spacing.lg,
    textAlign: "center",
  },
  subtitle: {
    ...typography.footnote,
    color: c.tx2,
    marginTop: spacing.xs,
    marginBottom: spacing.xxl,
    textAlign: "center",
  },
  faceCircle: {
    width: 76,
    height: 76,
    borderRadius: radii.full,
    borderWidth: 1.5,
    borderColor: c.line2,
    backgroundColor: c.accDim,
    alignItems: "center",
    justifyContent: "center",
  },
  faceLabel: {
    ...typography.caption,
    color: c.tx2,
    marginTop: spacing.md,
  },
  errorText: {
    ...typography.caption,
    color: c.coral,
    marginTop: spacing.md,
    textAlign: "center",
  },
  primaryCta: {
    alignSelf: "stretch",
    marginTop: spacing.xxl,
  },
  fallback: {
    marginTop: spacing.lg,
    paddingVertical: spacing.sm,
  },
  fallbackLabel: {
    ...typography.footnote,
    fontFamily: family.sansSemibold,
    color: c.tx2,
  },
});
