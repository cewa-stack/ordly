/**
 * Ekran blokady - pokazywany przy zimnym starcie, gdy sesja (adres+token)
 * jest już zapisana i użytkownik wcześniej włączył biometrię. Prawdziwy
 * prompt systemowy Face ID/Touch ID/odcisku (patrz utils/biometric.ts) -
 * to jedyna droga wejścia poza wpisaniem hasła jeszcze raz.
 */
import * as React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { StatusBar } from "expo-status-bar";

import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { family, radii, spacing, typography } from "@/theme/typography";
import { useAuth } from "@/store/auth";
import { Ordlak } from "@/components/Ordlak";
import { GlowBackdrop } from "@/components/GlowBackdrop";
import { PrimaryButton } from "@/components/PrimaryButton";
import { FaceIdIcon } from "@/icons";

export function LockScreen() {
  const styles = useThemedStyles(createStyles);
  const { c } = useTheme();
  const { biometricLabel, unlockWithBiometric, useFallbackPasswordLogin, username } = useAuth();
  const [attempting, setAttempting] = React.useState(false);
  const [failed, setFailed] = React.useState(false);
  const attemptedOnMount = React.useRef(false);

  const tryUnlock = React.useCallback(async () => {
    setAttempting(true);
    setFailed(false);
    const ok = await unlockWithBiometric();
    setAttempting(false);
    if (!ok) {
      setFailed(true);
    }
  }, [unlockWithBiometric]);

  React.useEffect(() => {
    if (attemptedOnMount.current) {
      return;
    }
    attemptedOnMount.current = true;
    void tryUnlock();
  }, [tryUnlock]);

  return (
    <View style={styles.screen}>
      <StatusBar style="light" />
      <GlowBackdrop />
      <View style={styles.content}>
        <Ordlak state="sleep" size={92} />
        <Text style={styles.greeting}>
          {username ? `Witaj, ${username}` : "Witaj z powrotem"}
        </Text>
        <Text style={styles.subtitle}>Odblokuj ORDLY, żeby wrócić do sklepu.</Text>

        <Pressable
          onPress={() => void tryUnlock()}
          disabled={attempting}
          style={({ pressed }) => [styles.faceCircle, pressed && { opacity: 0.85 }]}
        >
          <FaceIdIcon size={30} color={c.acc} />
        </Pressable>
        <Text style={styles.faceLabel}>
          {attempting ? "Sprawdzam…" : `Dotknij, aby użyć ${biometricLabel}`}
        </Text>

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

        <Pressable onPress={useFallbackPasswordLogin} hitSlop={8} style={styles.fallback}>
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
  content: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
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
