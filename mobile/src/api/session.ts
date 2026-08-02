/**
 * Bieżąca sesja (adres ORDLY API + token) w prostej zmiennej modułowej.
 *
 * `AuthProvider` (src/store/auth.tsx) jest jedynym miejscem, które to
 * zapisuje (po odczycie/zapisie do `expo-secure-store`) - `client.ts`
 * tylko odczytuje, żeby zapytania react-query nie musiały przeciągać
 * tokena przez każdy hook z osobna.
 */
export interface Session {
  baseUrl: string | null;
  token: string | null;
}

let session: Session = { baseUrl: null, token: null };

export function setSession(next: Session): void {
  session = next;
}

export function getSession(): Session {
  return session;
}
