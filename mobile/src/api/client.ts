/**
 * Klient HTTP ORDLY API - cienki wrapper nad `fetch`. Adres bazowy i token
 * pochodzą z `getSession()` (ustawiane przez `AuthProvider` po odczycie
 * z `expo-secure-store`) - żaden hook nie zarządza nimi samodzielnie.
 */
import { notifyUnauthorized } from "./authEvents";
import { getSession } from "./session";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** 401 => token jest zły/wygasł; ekran wywołujący powinien wylogować użytkownika. */
export function isUnauthorized(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 401;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { baseUrl, token } = getSession();
  if (!baseUrl) {
    throw new ApiError("Brak skonfigurowanego adresu ORDLY API", 0);
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init.headers as Record<string, string>) ?? {}),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      "Nie udało się połączyć z ORDLY API - sprawdź adres i połączenie (Tailscale/Wi-Fi)",
      0
    );
  }

  if (!response.ok) {
    let detail = response.statusText || `Błąd HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // odpowiedź nie jest JSON-em - zostaw domyślny komunikat
    }
    if (response.status === 401) {
      notifyUnauthorized();
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  get: <T,>(path: string): Promise<T> => request<T>(path),
  post: <T,>(path: string, body?: unknown): Promise<T> =>
    request<T>(path, {
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  del: <T,>(path: string, body?: unknown): Promise<T> =>
    request<T>(path, {
      method: "DELETE",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
};

/** Sprawdzenie połączenia bez tokena - używane na ekranie logowania. */
export async function checkHealth(baseUrl: string): Promise<boolean> {
  try {
    const response = await fetch(`${baseUrl}/api/v1/health`);
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Login+hasło -> token. Wywoływane, zanim jakikolwiek token istnieje,
 * więc nie może iść przez `api.post` (ten czyta token z `getSession()`).
 */
export async function loginWithCredentials(
  baseUrl: string,
  username: string,
  password: string
): Promise<{ token: string }> {
  let response: Response;
  try {
    response = await fetch(`${baseUrl}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  } catch {
    throw new ApiError(
      "Nie udało się połączyć z ORDLY API - sprawdź adres i połączenie (Tailscale/Wi-Fi)",
      0
    );
  }

  if (!response.ok) {
    let detail = response.statusText || `Błąd HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // odpowiedź nie jest JSON-em - zostaw domyślny komunikat
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as { token: string };
}
