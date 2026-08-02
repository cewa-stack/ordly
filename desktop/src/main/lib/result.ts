/**
 * Kontrakt wynikow IPC main -> renderer. Electron przy rzuceniu bledu
 * w ipcMain.handle serializuje do renderera tylko `message` (traci
 * dodatkowe pola typu `status`) - zwracanie jawnego discriminated
 * union zamiast throw pozwala UI odroznic 401 od 429 od braku sieci.
 */
import { ApiError } from "./apiClient";

export type Result<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; message: string };

export async function toResult<T>(fn: () => Promise<T>): Promise<Result<T>> {
  try {
    const data = await fn();
    return { ok: true, data };
  } catch (err) {
    if (err instanceof ApiError) {
      return { ok: false, status: err.status, message: err.message };
    }
    const message = err instanceof Error ? err.message : "Coś poszło nie tak. Spróbuj ponownie.";
    return { ok: false, status: 0, message };
  }
}
