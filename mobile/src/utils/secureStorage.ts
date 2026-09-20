/**
 * Przechowywanie adresu API i tokena - Keychain/Keystore na natywnym
 * iOS/Androidzie (`expo-secure-store`), `localStorage` na webie.
 *
 * `expo-secure-store` **nie ma** działającej implementacji web (rzuca
 * `getValueWithKeyAsync is not a function` przy każdym wywołaniu) - stąd
 * ta warstwa zamiast wołania SecureStore wprost z `store/auth.tsx`.
 * `localStorage` nie daje takiej samej ochrony jak Keychain, ale to
 * standardowy, akceptowalny kompromis dla PWA (przeglądarka i tak nie
 * ma odpowiednika Keychain) - token i tak wymaga fizycznego dostępu do
 * odblokowanego urządzenia.
 */
import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

export async function getItemAsync(key: string): Promise<string | null> {
  if (Platform.OS === "web") {
    return typeof localStorage !== "undefined" ? localStorage.getItem(key) : null;
  }
  return SecureStore.getItemAsync(key);
}

export async function setItemAsync(key: string, value: string): Promise<void> {
  if (Platform.OS === "web") {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(key, value);
    }
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

export async function deleteItemAsync(key: string): Promise<void> {
  if (Platform.OS === "web") {
    if (typeof localStorage !== "undefined") {
      localStorage.removeItem(key);
    }
    return;
  }
  await SecureStore.deleteItemAsync(key);
}

/**
 * Wybor atmosfery (sekcja 11): `auto` wedlug godziny albo reczne
 * nadpisanie. Trzyma sie obok tokena, bo to ta sama warstwa
 * "ustawienie, ktore ma przezyc restart" - ale NIE jest tajemnica,
 * wiec brak Keychain na webie niczego tu nie psuje.
 */
const THEME_KEY = "ordly.theme";

export async function loadThemePreference(): Promise<string | null> {
  try {
    return await getItemAsync(THEME_KEY);
  } catch {
    // Zablokowany localStorage (tryb prywatny) nie moze wywrocic startu
    // aplikacji - brak zapisanego wyboru znaczy po prostu "auto".
    return null;
  }
}

export async function saveThemePreference(value: string): Promise<void> {
  try {
    await setItemAsync(THEME_KEY, value);
  } catch {
    // Nieudany zapis jest do przezycia: atmosfera zadziala w tej sesji,
    // tylko nie przezyje restartu.
  }
}
