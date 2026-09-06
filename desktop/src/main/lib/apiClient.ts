/**
 * Klient HTTP do ORDLY API. Zyje wylacznie w main procesie - renderer
 * nigdy nie widzi surowego tokenu ani nie woła fetch() bezposrednio,
 * zeby token nie byl osiagalny z poziomu DevTools/zaleznosci npm w
 * warstwie UI.
 */

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const NETWORK_ERROR_MESSAGE =
  "Nie widzę ORDLY API pod tym adresem. Sprawdź, czy backend działa i czy komputer jest w tej samej sieci (lub Tailscale).";

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  body?: unknown;
}

/**
 * Wykonuje jedno żądanie do ORDLY API pod `${baseUrl}${path}`.
 *
 * `token` moze byc `null` wylacznie dla `/auth/login` - kazdy inny
 * endpoint ORDLY API wymaga `Authorization: Bearer <token>`
 * (app/api/auth.py::require_api_token).
 */
export async function apiRequest<T>(
  baseUrl: string,
  token: string | null,
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const url = `${baseUrl}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError(0, NETWORK_ERROR_MESSAGE);
  }

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload?.detail;
    } catch {
      // odpowiedz bez JSON-a (np. 502 z proxy) - zostaw domyslny komunikat
    }
    if (response.status === 401) {
      throw new ApiError(401, detail ?? "Nieprawidłowa nazwa użytkownika lub hasło");
    }
    if (response.status === 429) {
      throw new ApiError(429, detail ?? "Zbyt wiele prób. Spróbuj ponownie za chwilę.");
    }
    throw new ApiError(response.status, detail ?? `Błąd serwera ORDLY (${response.status})`);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
