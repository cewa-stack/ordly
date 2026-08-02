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
