/**
 * Odblokowanie biometryczne (Face ID / Touch ID / odcisk palca).
 *
 * To NIE jest ponowne logowanie do serwera - to lokalna "kłódka" na już
 * zdobytą sesję (adres API + token), dokładnie jak w 1Password czy
 * aplikacjach bankowych: hasło administratora (`admin`/`admin` domyślnie)
 * loguje raz i zdobywa token; biometria później tylko potwierdza "to
 * nadal Ty", żeby nie wpisywać hasła za każdym otwarciem.
 *
 * Natywne iOS/Android: `expo-local-authentication` woła prawdziwe Face
 * ID/Touch ID/czytnik linii papilarnych systemu operacyjnego.
 *
 * Web (PWA): WebAuthn (`navigator.credentials`) z
 * `authenticatorAttachment: "platform"` - to ten sam mechanizm, którego
 * używa np. logowanie do banku przez Face ID w Safari na iPhonie.
 * Wyzwanie (`challenge`) jest generowane lokalnie i NIE jest weryfikowane
 * na serwerze - świadomie, bo tu chronimy tylko lokalny dostęp do
 * urządzenia, a nie tworzymy drugiego, równoległego systemu logowania.
 * Prawdziwe uwierzytelnienie nadal wykonuje `/api/v1/auth/login`.
 */
import { Platform } from "react-native";
import * as LocalAuthentication from "expo-local-authentication";

import { deleteItemAsync, getItemAsync, setItemAsync } from "./secureStorage";

const CREDENTIAL_ID_KEY = "ordly_webauthn_credential_id";

export type BiometricLabel = "Face ID" | "Touch ID" | "Odcisk palca" | "Biometria";

function base64UrlToBuffer(base64Url: string): ArrayBuffer {
  const padding = "=".repeat((4 - (base64Url.length % 4)) % 4);
  const base64 = (base64Url + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) {
    bytes[i] = raw.charCodeAt(i);
  }
  return bytes.buffer;
}

function randomChallenge(): Uint8Array {
  const bytes = new Uint8Array(32);
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
  }
  return bytes;
}

function webAuthnSupported(): boolean {
  return (
    Platform.OS === "web" &&
    typeof window !== "undefined" &&
    typeof window.PublicKeyCredential !== "undefined" &&
    typeof navigator !== "undefined" &&
    typeof navigator.credentials !== "undefined"
  );
}

/** Czy urządzenie w ogóle ma sprzęt i skonfigurowaną biometrię. */
export async function isBiometricAvailable(): Promise<boolean> {
  if (Platform.OS === "web") {
    if (!webAuthnSupported()) {
      return false;
    }
    try {
      const PKC = window.PublicKeyCredential as unknown as {
        isUserVerifyingPlatformAuthenticatorAvailable?: () => Promise<boolean>;
      };
      if (typeof PKC.isUserVerifyingPlatformAuthenticatorAvailable !== "function") {
        return false;
      }
      return await PKC.isUserVerifyingPlatformAuthenticatorAvailable();
    } catch {
      return false;
    }
  }

  try {
    const [hasHardware, isEnrolled] = await Promise.all([
      LocalAuthentication.hasHardwareAsync(),
      LocalAuthentication.isEnrolledAsync(),
    ]);
    return hasHardware && isEnrolled;
  } catch {
    return false;
  }
}

/** Nazwa do wyświetlenia w UI ("Face ID", "Touch ID", "Odcisk palca"...). */
export async function getBiometricLabel(): Promise<BiometricLabel> {
  if (Platform.OS === "ios") {
    return "Face ID";
  }
  if (Platform.OS === "web") {
    return "Face ID";
  }
  try {
    const types = await LocalAuthentication.supportedAuthenticationTypesAsync();
    if (types.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)) {
      return "Face ID";
    }
    if (types.includes(LocalAuthentication.AuthenticationType.FINGERPRINT)) {
      return "Odcisk palca";
    }
  } catch {
    // ignore - fallback poniżej
  }
  return "Biometria";
}

/**
 * Włącza biometrię: na webie tworzy klucz WebAuthn i zapisuje jego id,
 * na natywnych po prostu potwierdza, że sprzęt działa (samo odblokowanie
 * używa systemowego Face ID/Touch ID, bez osobnej rejestracji).
 */
export async function enrollBiometric(username: string): Promise<boolean> {
  if (Platform.OS === "web") {
    if (!webAuthnSupported()) {
      return false;
    }
    try {
      const credential = (await navigator.credentials.create({
        publicKey: {
          challenge: randomChallenge(),
          rp: { name: "ORDLY", id: window.location.hostname },
          user: {
            id: randomChallenge(),
            name: username,
            displayName: "ORDLY",
          },
          pubKeyCredParams: [
            { type: "public-key", alg: -7 },
            { type: "public-key", alg: -257 },
          ],
          authenticatorSelection: {
            authenticatorAttachment: "platform",
            userVerification: "required",
            residentKey: "preferred",
          },
          timeout: 60000,
          attestation: "none",
        },
      })) as PublicKeyCredential | null;

      if (!credential) {
        return false;
      }
      await setItemAsync(CREDENTIAL_ID_KEY, credential.id);
      return true;
    } catch {
      return false;
    }
  }

  // Natywnie: enrollBiometric to tylko potwierdzenie działania sprzętu -
  // realny "klucz" to system operacyjny, nic nie trzeba zapisywać.
  return isBiometricAvailable();
}

/** Odblokowanie - prawdziwy prompt systemowy Face ID/Touch ID/odcisku. */
export async function unlockWithBiometric(promptMessage = "Odblokuj ORDLY"): Promise<boolean> {
  if (Platform.OS === "web") {
    const storedId = await getItemAsync(CREDENTIAL_ID_KEY);
    if (!storedId || !webAuthnSupported()) {
      return false;
    }
    try {
      const assertion = await navigator.credentials.get({
        publicKey: {
          challenge: randomChallenge(),
          allowCredentials: [
            { type: "public-key", id: base64UrlToBuffer(storedId) },
          ],
          userVerification: "required",
          timeout: 60000,
        },
      });
      return Boolean(assertion);
    } catch {
      return false;
    }
  }

  try {
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage,
      cancelLabel: "Anuluj",
      disableDeviceFallback: false,
    });
    return result.success;
  } catch {
    return false;
  }
}

export async function clearBiometricEnrollment(): Promise<void> {
  await deleteItemAsync(CREDENTIAL_ID_KEY);
}
