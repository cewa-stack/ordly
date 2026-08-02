/**
 * Propozycja włączenia Face ID/Touch ID/odcisku - pokazywana raz, od razu
 * po pierwszym udanym zalogowaniu hasłem, tylko gdy sprzęt na to pozwala
 * (`biometricAvailable`, patrz store/auth.tsx). Zgodne z wzorcem Apple
 * "pre-permission priming" z onboardingu (§2 specyfikacji) - wyjaśniamy
 * korzyść, zanim pojawi się systemowy prompt.
 */
import * as React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { useAuth } from "@/store/auth";
import { PrimaryButton } from "@/components/PrimaryButton";
import { Mascot } from "@/components/Mascot";
import { GlowBackdrop } from "@/components/GlowBackdrop";
import { FaceIdIcon } from "@/icons";

export function BiometricOptInScreen() {
  const { biometricLabel, confirmBiometricEnroll, skipBiometricPrompt } = useAuth();
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState(false);

  async function handleEnable() {
    setBusy(true);
    setError(false);
    const ok = await confirmBiometricEnroll();
    setBusy(false);
    if (!ok) {
      setError(true);
    }
  }

  return (
    <View style={styles.screen}>
      <GlowBackdrop />
      <View style={styles.content}>
        <Mascot size={88} />

        <View style={styles.faceCircle}>
          <FaceIdIcon size={34} color={colors.primary} />
        </View>

        <Text style={styles.title}>Włączyć {biometricLabel}?</Text>
        <Text style={styles.subtitle}>
          Następnym razem odblokujesz ORDLY jednym spojrzeniem albo dotknięciem — bez wpisywania
          hasła. Hasło zawsze zostaje jako zapasowa droga logowania.
        </Text>

        {error ? (
          <Text style={styles.error}>
            Nie udało się włączyć {biometricLabel} — spróbuj ponownie albo pomiń ten krok.
          </Text>
        ) : null}

        <PrimaryButton
          label={`Włącz ${biometricLabel}`}
          onPress={() => void handleEnable()}
          loading={busy}
          style={styles.cta}
        />
        <Pressable onPress={skipBiometricPrompt} hitSlop={8} style={styles.skip}>
          <Text style={styles.skipLabel}>Nie teraz</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
  },
  faceCircle: {
    width: 88,
    height: 88,
    borderRadius: radii.full,
    borderWidth: 1.5,
    borderColor: colors.primaryBorder,
    backgroundColor: colors.primaryTint,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.xl,
  },
  title: {
    ...typography.title1,
    fontSize: 22,
    color: colors.text,
    marginTop: spacing.xl,
    textAlign: "center",
  },
  subtitle: {
    ...typography.footnote,
    color: colors.textSecondary,
    textAlign: "center",
    marginTop: spacing.sm,
    maxWidth: 280,
    lineHeight: 19,
  },
  error: {
    ...typography.caption,
    color: colors.danger,
    textAlign: "center",
    marginTop: spacing.md,
  },
  cta: {
    alignSelf: "stretch",
    marginTop: spacing.xxl,
  },
  skip: {
    marginTop: spacing.lg,
    paddingVertical: spacing.sm,
  },
  skipLabel: {
    ...typography.footnote,
    fontWeight: "600",
    color: colors.textSecondary,
  },
});
