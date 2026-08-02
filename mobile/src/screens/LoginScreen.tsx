/**
 * Logowanie do ORDLY API - login+hasło (domyślnie admin/admin, patrz
 * ORDLY_ADMIN_USERNAME/ORDLY_ADMIN_PASSWORD w .env backendu) zamiast
 * ręcznego wklejania tokena. Token nadal istnieje (ORDLY_API_TOKEN) -
 * `loginWithPassword` w AuthProvider zdobywa go automatycznie przez
 * `/api/v1/auth/login` (app/api/endpoints/auth.py) i zapamiętuje.
 *
 * Adres API pozostaje wymagany (apka musi wiedzieć, gdzie jest Twoje
 * Raspberry Pi) - zwykle Tailscale MagicDNS, patrz docs/01_app.md §4.
 */
import * as React from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { ApiError } from "@/api/client";
import { useAuth } from "@/store/auth";
import { FormField } from "@/components/FormField";
import { PrimaryButton } from "@/components/PrimaryButton";
import { Mascot } from "@/components/Mascot";
import { GlowBackdrop } from "@/components/GlowBackdrop";
import { EyeIcon, EyeOffIcon, LockIcon, ServerIcon, UserIcon } from "@/icons";

export function LoginScreen() {
  const { baseUrl: storedBaseUrl, username: storedUsername, loginWithPassword, sessionExpiredMessage, clearSessionExpiredMessage } =
    useAuth();
  const [serverUrl, setServerUrl] = React.useState(storedBaseUrl ?? "http://");
  const [username, setUsername] = React.useState(storedUsername ?? "admin");
  const [password, setPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(sessionExpiredMessage);

  const canSubmit =
    serverUrl.trim().length > 8 &&
    username.trim().length > 0 &&
    password.length > 0 &&
    !isSubmitting;

  async function handleSubmit() {
    setError(null);
    clearSessionExpiredMessage();
    setIsSubmitting(true);
    try {
      await loginWithPassword(serverUrl, username.trim(), password);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          err.status === 429
            ? err.message
            : err.status === 401
              ? err.message
              : "Nie widzę ORDLY API pod tym adresem. Sprawdź, czy backend działa i czy telefon jest w tej samej sieci (lub Tailscale)."
        );
      } else {
        setError("Coś poszło nie tak. Spróbuj ponownie.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <StatusBar style="light" />
      <GlowBackdrop />
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <Mascot size={92} style={styles.mascot} />
        <Text style={styles.brandName}>ORDLY</Text>
        <Text style={styles.title}>Witaj z powrotem</Text>
        <Text style={styles.subtitle}>
          Twój sklep czekał. Połącz się ze swoim ORDLY na Raspberry Pi.
        </Text>

        <View style={styles.form}>
          <FormField
            label="Adres serwera"
            icon={<ServerIcon size={17} color={colors.primary} />}
            value={serverUrl}
            onChangeText={setServerUrl}
            placeholder="http://raspberrypi:8000"
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
            error={Boolean(error)}
          />
          <FormField
            label="Login"
            icon={<UserIcon size={17} color={colors.textSecondary} />}
            value={username}
            onChangeText={setUsername}
            placeholder="admin"
            autoCapitalize="none"
            autoCorrect={false}
            error={Boolean(error)}
          />
          <FormField
            label="Hasło"
            icon={<LockIcon size={17} color={colors.textSecondary} />}
            value={password}
            onChangeText={setPassword}
            placeholder="domyślnie: admin"
            autoCapitalize="none"
            autoCorrect={false}
            secureTextEntry={!showPassword}
            error={Boolean(error)}
            trailing={
              showPassword ? (
                <EyeOffIcon size={17} color={colors.textSecondary} />
              ) : (
                <EyeIcon size={17} color={colors.textSecondary} />
              )
            }
            onTrailingPress={() => setShowPassword((v) => !v)}
          />
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <PrimaryButton
          label="Połącz z ORDLY"
          onPress={handleSubmit}
          disabled={!canSubmit}
          loading={isSubmitting}
          style={styles.cta}
        />

        {isSubmitting ? null : (
          <Text style={styles.hint}>
            Domyślne dane logowania to <Text style={styles.hintBold}>admin</Text> /{" "}
            <Text style={styles.hintBold}>admin</Text> — zmień je w pliku .env po pierwszym
            uruchomieniu.
          </Text>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    flexGrow: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.xxl,
  },
  mascot: {
    marginBottom: spacing.md,
  },
  brandName: {
    fontSize: 12.5,
    fontWeight: "800",
    letterSpacing: 5,
    color: colors.text,
  },
  title: {
    ...typography.title1,
    fontSize: 22,
    lineHeight: 28,
    color: colors.text,
    textAlign: "center",
    marginTop: spacing.lg,
  },
  subtitle: {
    ...typography.footnote,
    color: colors.textSecondary,
    textAlign: "center",
    marginTop: spacing.xs,
    marginBottom: spacing.xl,
    maxWidth: 260,
  },
  form: {
    alignSelf: "stretch",
    gap: spacing.sm,
  },
  error: {
    ...typography.caption,
    color: colors.danger,
    lineHeight: 17,
    alignSelf: "stretch",
    marginTop: spacing.sm,
  },
  cta: {
    alignSelf: "stretch",
    marginTop: spacing.lg,
  },
  hint: {
    ...typography.caption,
    fontSize: 11.5,
    color: colors.textDim,
    textAlign: "center",
    marginTop: spacing.md,
    lineHeight: 16,
  },
  hintBold: {
    color: colors.textSecondary,
    fontWeight: "700",
  },
});
