/**
 * Logowanie do ORDLY API - login+hasło (domyślnie admin/admin, patrz
 * ORDLY_ADMIN_USERNAME/ORDLY_ADMIN_PASSWORD w .env backendu) zamiast
 * ręcznego wklejania tokena. Token nadal istnieje (ORDLY_API_TOKEN) -
 * `loginWithPassword` w AuthProvider zdobywa go automatycznie przez
 * `/api/v1/auth/login` (app/api/endpoints/auth.py) i zapamiętuje.
 *
 * Adres API pozostaje wymagany (apka musi wiedzieć, gdzie jest Twoje
 * Raspberry Pi) - zwykle Tailscale MagicDNS, patrz docs/01_app.md §4.
 *
 * Pole adresu startuje od `https://`: przez Tailscale działa WYŁĄCZNIE
 * https, a dawne „http://” było pułapką, która kosztowała wieczór
 * debugowania. Nie ma już też podpowiedzi „admin / admin” - ekran
 * logowania widzi każdy, kto trafi na adres Pi.
 */
import * as React from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { family, radii, spacing, typography } from "@/theme/typography";
import { ApiError } from "@/api/client";
import { useAuth } from "@/store/auth";
import { FormField } from "@/components/FormField";
import { PrimaryButton } from "@/components/PrimaryButton";
import { Ordlak } from "@/components/Ordlak";
import { Waybill } from "@/components/Waybill";
import { EyeIcon, EyeOffIcon, LockIcon, ServerIcon, UserIcon } from "@/icons";

export function LoginScreen() {
  const styles = useThemedStyles(createStyles);
  const { c, mode } = useTheme();
  const { width: screenWidth } = useWindowDimensions();
  // Etykieta na górze nie może wejść pod zegar, gdy formularz jest dłuższy
  // niż ekran (mały telefon, otwarta klawiatura).
  const insets = useSafeAreaInsets();
  const { baseUrl: storedBaseUrl, username: storedUsername, loginWithPassword, sessionExpiredMessage, clearSessionExpiredMessage } =
    useAuth();
  const [serverUrl, setServerUrl] = React.useState(storedBaseUrl ?? "https://");
  const [username, setUsername] = React.useState(storedUsername ?? "");
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
      <StatusBar style={mode === "day" ? "dark" : "light"} />
      <ScrollView
        contentContainerStyle={[styles.content, { paddingTop: insets.top + spacing.lg }]}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {/* Mniejsza niż na blokadzie - tu pierwszeństwo ma formularz. */}
        <Waybill width={Math.min(260, screenWidth - 2 * spacing.xl)} />
        <Ordlak state="idle" size={92} style={styles.mascot} />
        <Text style={styles.brandName}>ORDLY</Text>
        <Text style={styles.title}>Witaj z powrotem</Text>
        <Text style={styles.subtitle}>
          Twój sklep czekał. Połącz się ze swoim ORDLY na Raspberry Pi.
        </Text>

        <View style={styles.form}>
          <FormField
            label="Adres serwera"
            icon={<ServerIcon size={17} color={c.acc} />}
            value={serverUrl}
            onChangeText={setServerUrl}
            placeholder="https://twoje-pi.tailnet.ts.net"
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
            error={Boolean(error)}
          />
          <FormField
            label="Login"
            icon={<UserIcon size={17} color={c.tx2} />}
            value={username}
            onChangeText={setUsername}
            placeholder="Login"
            autoCapitalize="none"
            autoCorrect={false}
            error={Boolean(error)}
          />
          <FormField
            label="Hasło"
            icon={<LockIcon size={17} color={c.tx2} />}
            value={password}
            onChangeText={setPassword}
            placeholder="Hasło"
            autoCapitalize="none"
            autoCorrect={false}
            secureTextEntry={!showPassword}
            error={Boolean(error)}
            trailing={
              showPassword ? (
                <EyeOffIcon size={17} color={c.tx2} />
              ) : (
                <EyeIcon size={17} color={c.tx2} />
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
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const createStyles = (c: Palette) =>
  StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: c.bg,
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
    fontFamily: family.display,
    letterSpacing: 5,
    color: c.tx,
  },
  title: {
    ...typography.title1,
    fontSize: 22,
    lineHeight: 28,
    color: c.tx,
    textAlign: "center",
    marginTop: spacing.lg,
  },
  subtitle: {
    ...typography.footnote,
    color: c.tx2,
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
    color: c.coral,
    lineHeight: 17,
    alignSelf: "stretch",
    marginTop: spacing.sm,
  },
  cta: {
    alignSelf: "stretch",
    marginTop: spacing.lg,
  },
});
