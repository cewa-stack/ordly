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
  method?: "GET" | "POST" | "DELETE" | "PATCH";
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

/** Plik przekazany z renderera jako zwykłe bajty (IPC nie przenosi obiektów `File`). */
export interface UploadFilePart {
  fieldName: string;
  fileName: string;
  mimeType: string;
  bytes: Uint8Array;
}

/**
 * Wysyła `multipart/form-data` - potrzebne tam, gdzie razem z polami
 * lecą pliki (dziś: zdjęcia produktu do Ordlaka).
 *
 * Osobna funkcja zamiast rozbudowy `apiRequest`, bo tryb multipart różni
 * się w każdym punkcie: nie ustawiamy `Content-Type` (robi to `fetch` sam,
 * razem z `boundary`), ciało nie jest JSON-em, a pola muszą być stringami.
 */
export async function apiUpload<T>(
  baseUrl: string,
  token: string,
  path: string,
  fields: Record<string, string | number>,
  files: UploadFilePart[] = []
): Promise<T> {
  const form = new FormData();
  for (const [key, value] of Object.entries(fields)) {
    form.append(key, String(value));
  }
  for (const file of files) {
    // Kopia do świeżego ArrayBuffer - bufor zza mostka IPC bywa widokiem
    // na większy blok pamięci i `Blob` zabrałby wtedy za dużo bajtów.
    const copy = new Uint8Array(file.bytes.byteLength);
    copy.set(file.bytes);
    form.append(
      file.fieldName,
      new Blob([copy], { type: file.mimeType }),
      file.fileName
    );
  }

  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
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
      // odpowiedz bez JSON-a - zostaw domyslny komunikat
    }
    throw new ApiError(response.status, detail ?? `Błąd serwera ORDLY (${response.status})`);
  }

  return (await response.json()) as T;
}
