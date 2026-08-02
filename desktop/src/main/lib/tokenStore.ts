/**
 * Trwałe przechowywanie sesji ORDLY (adres serwera, login, token) w
 * main procesie. Token jest szyfrowany przez `safeStorage` (na
 * Windows: DPAPI powiazane z kontem uzytkownika) przed zapisem na
 * dysk - plik na dysku bez odblokowanego konta Windows jest
 * bezuzyteczny.
 */
import { app, safeStorage } from "electron";
import { existsSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { ApiError } from "./apiClient";

export interface StoredSession {
  baseUrl: string;
  username: string;
  token: string;
}

function sessionFilePath(): string {
  return join(app.getPath("userData"), "session.enc");
}

let cache: StoredSession | null | undefined;

export function getSession(): StoredSession | null {
  if (cache !== undefined) {
    return cache;
  }
  const path = sessionFilePath();
  if (!existsSync(path) || !safeStorage.isEncryptionAvailable()) {
    cache = null;
    return null;
  }
  try {
    const encrypted = readFileSync(path);
    const decrypted = safeStorage.decryptString(encrypted);
    cache = JSON.parse(decrypted) as StoredSession;
  } catch {
    cache = null;
  }
  return cache;
}

export function saveSession(session: StoredSession): void {
  if (!safeStorage.isEncryptionAvailable()) {
    throw new Error(
      "Bezpieczne szyfrowanie systemowe jest niedostępne na tym komputerze - nie można zapisać sesji."
    );
  }
  const encrypted = safeStorage.encryptString(JSON.stringify(session));
  writeFileSync(sessionFilePath(), encrypted);
  cache = session;
}

export function clearSession(): void {
  const path = sessionFilePath();
  if (existsSync(path)) {
    unlinkSync(path);
  }
  cache = null;
}

/** Sesja albo 401 - uzywane przez kazdy handler IPC poza auth:*. */
export function requireSession(): StoredSession {
  const session = getSession();
  if (!session) {
    throw new ApiError(401, "Brak aktywnej sesji - zaloguj się ponownie.");
  }
  return session;
}
