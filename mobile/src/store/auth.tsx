/**
 * Stan logowania z ORDLY API - login+hasło zdobywa token raz (patrz
 * `api/client.ts` -> `loginWithCredentials`), a Face ID/Touch ID/odcisk
 * później tylko lokalnie odblokowuje dostęp do już zapisanej sesji
 * (adres + token), zamiast wpisywania hasła za każdym otwarciem apki -
 * patrz `utils/biometric.ts` po pełne wyjaśnienie tego modelu.
 */
import * as React from "react";

import { loginWithCredentials } from "@/api/client";
import { setUnauthorizedHandler } from "@/api/authEvents";
import { setSession } from "@/api/session";
import { deleteItemAsync, getItemAsync, setItemAsync } from "@/utils/secureStorage";
import {
  type BiometricLabel,
  clearBiometricEnrollment,
  enrollBiometric,
  getBiometricLabel,
  isBiometricAvailable,
  unlockWithBiometric as unlockWithBiometricUtil,
} from "@/utils/biometric";

const BASE_URL_KEY = "ordly_api_base_url";
const TOKEN_KEY = "ordly_api_token";
const USERNAME_KEY = "ordly_username";
const BIOMETRIC_FLAG_KEY = "ordly_biometric_enabled";

interface AuthState {
  isLoading: boolean;
  /** Adres + token zapisane (niezależnie od tego, czy ekran jest zablokowany). */
  hasSession: boolean;
  /** Sesja jest zapisana, ale czeka na potwierdzenie Face ID po zimnym starcie. */
  isLocked: boolean;
  /** Sesja odblokowana i gotowa do użycia - to wtedy pokazuje się Main. */
  isAuthenticated: boolean;
  /** Pokazać ekran "Włącz Face ID?" - tylko raz, tuż po świeżym logowaniu hasłem. */
  needsBiometricPrompt: boolean;
  biometricAvailable: boolean;
  biometricEnabled: boolean;
  biometricLabel: BiometricLabel;
  baseUrl: string | null;
  username: string | null;
  /** Ustawiane po globalnym 401 - LoginScreen pokazuje komunikat. */
  sessionExpiredMessage: string | null;
  clearSessionExpiredMessage: () => void;
  loginWithPassword: (baseUrl: string, username: string, password: string) => Promise<void>;
  confirmBiometricEnroll: () => Promise<boolean>;
  skipBiometricPrompt: () => void;
  unlockWithBiometric: () => Promise<boolean>;
  useFallbackPasswordLogin: () => void;
  disableBiometric: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = React.createContext<AuthState | undefined>(undefined);

function normalizeBaseUrl(rawUrl: string): string {
  return rawUrl.trim().replace(/\/+$/, "");
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoading, setIsLoading] = React.useState(true);
  const [baseUrl, setBaseUrl] = React.useState<string | null>(null);
  const [token, setToken] = React.useState<string | null>(null);
  const [username, setUsernameState] = React.useState<string | null>(null);
  const [isLocked, setIsLocked] = React.useState(false);
  const [needsBiometricPrompt, setNeedsBiometricPrompt] = React.useState(false);
  const [biometricAvailable, setBiometricAvailable] = React.useState(false);
  const [biometricEnabled, setBiometricEnabled] = React.useState(false);
  const [biometricLabel, setBiometricLabel] = React.useState<BiometricLabel>("Biometria");
  const [sessionExpiredMessage, setSessionExpiredMessage] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;

    async function restore() {
      try {
        const [storedBaseUrl, storedToken, storedUsername, storedBiometricFlag, label, available] =
          await Promise.all([
            getItemAsync(BASE_URL_KEY),
            getItemAsync(TOKEN_KEY),
            getItemAsync(USERNAME_KEY),
            getItemAsync(BIOMETRIC_FLAG_KEY),
            getBiometricLabel(),
            isBiometricAvailable(),
          ]);
        if (cancelled) {
          return;
        }
        setSession({ baseUrl: storedBaseUrl, token: storedToken });
        setBaseUrl(storedBaseUrl);
        setToken(storedToken);
        setUsernameState(storedUsername);
        setBiometricLabel(label);
        setBiometricAvailable(available);
        const biometricOn = storedBiometricFlag === "1";
        setBiometricEnabled(biometricOn);
        if (storedBaseUrl && storedToken && biometricOn) {
          setIsLocked(true);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void restore();
    return () => {
      cancelled = true;
    };
  }, []);

  const loginWithPassword = React.useCallback(
    async (rawBaseUrl: string, user: string, password: string) => {
      const normalized = normalizeBaseUrl(rawBaseUrl);
      const { token: newToken } = await loginWithCredentials(normalized, user, password);
      await Promise.all([
        setItemAsync(BASE_URL_KEY, normalized),
        setItemAsync(TOKEN_KEY, newToken),
        setItemAsync(USERNAME_KEY, user),
      ]);
      setSession({ baseUrl: normalized, token: newToken });
      setBaseUrl(normalized);
      setToken(newToken);
      setUsernameState(user);
      setIsLocked(false);
      setSessionExpiredMessage(null);

      const available = await isBiometricAvailable();
      setBiometricAvailable(available);
      const alreadyEnabled = (await getItemAsync(BIOMETRIC_FLAG_KEY)) === "1";
      setNeedsBiometricPrompt(available && !alreadyEnabled);
    },
    []
  );

  const confirmBiometricEnroll = React.useCallback(async () => {
    if (!username) {
      setNeedsBiometricPrompt(false);
      return false;
    }
    const success = await enrollBiometric(username);
    if (success) {
      await setItemAsync(BIOMETRIC_FLAG_KEY, "1");
      setBiometricEnabled(true);
    }
    setNeedsBiometricPrompt(false);
    return success;
  }, [username]);

  const skipBiometricPrompt = React.useCallback(() => {
    setNeedsBiometricPrompt(false);
  }, []);

  const unlockWithBiometric = React.useCallback(async () => {
    const ok = await unlockWithBiometricUtil("Odblokuj ORDLY");
    if (ok) {
      setIsLocked(false);
    }
    return ok;
  }, []);

  const useFallbackPasswordLogin = React.useCallback(() => {
    // Zostawia adres API i login w stanie (prefill), tylko usuwa token z
    // pamięci procesu - to pokazuje LoginScreen z prośbą o ponowne hasło,
    // bez ruszania tego, co już bezpiecznie leży w SecureStore.
    setIsLocked(false);
    setToken(null);
  }, []);

  const disableBiometric = React.useCallback(async () => {
    await Promise.all([deleteItemAsync(BIOMETRIC_FLAG_KEY), clearBiometricEnrollment()]);
    setBiometricEnabled(false);
  }, []);

  const logout = React.useCallback(async () => {
    await Promise.all([
      deleteItemAsync(BASE_URL_KEY),
      deleteItemAsync(TOKEN_KEY),
      deleteItemAsync(USERNAME_KEY),
      deleteItemAsync(BIOMETRIC_FLAG_KEY),
      clearBiometricEnrollment(),
    ]);
    setSession({ baseUrl: null, token: null });
    setBaseUrl(null);
    setToken(null);
    setUsernameState(null);
    setIsLocked(false);
    setNeedsBiometricPrompt(false);
    setBiometricEnabled(false);
  }, []);

  const clearSessionExpiredMessage = React.useCallback(() => {
    setSessionExpiredMessage(null);
  }, []);

  React.useEffect(() => {
    setUnauthorizedHandler(() => {
      setSessionExpiredMessage("Sesja wygasła — zaloguj się ponownie.");
      void logout();
    });
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  const hasSession = Boolean(baseUrl && token);

  const value = React.useMemo<AuthState>(
    () => ({
      isLoading,
      hasSession,
      isLocked,
      isAuthenticated: hasSession && !isLocked,
      needsBiometricPrompt,
      biometricAvailable,
      biometricEnabled,
      biometricLabel,
      baseUrl,
      username,
      sessionExpiredMessage,
      clearSessionExpiredMessage,
      loginWithPassword,
      confirmBiometricEnroll,
      skipBiometricPrompt,
      unlockWithBiometric,
      useFallbackPasswordLogin,
      disableBiometric,
      logout,
    }),
    [
      isLoading,
      hasSession,
      isLocked,
      needsBiometricPrompt,
      biometricAvailable,
      biometricEnabled,
      biometricLabel,
      baseUrl,
      username,
      sessionExpiredMessage,
      clearSessionExpiredMessage,
      loginWithPassword,
      confirmBiometricEnroll,
      skipBiometricPrompt,
      unlockWithBiometric,
      useFallbackPasswordLogin,
      disableBiometric,
      logout,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth musi być użyty wewnątrz <AuthProvider>");
  }
  return context;
}
