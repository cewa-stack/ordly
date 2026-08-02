/**
 * Most między `QueryClient` (utworzonym poza drzewem React w App.tsx) a
 * `AuthProvider` (w drzewie React) - potrzebny dla obsługi 401 z
 * docs/02_appdesign.md §7: "zły/wygasły token -> przekierowanie do
 * logowania". `QueryCache`/`MutationCache` nie mają dostępu do hooków,
 * więc `AuthProvider` rejestruje tu swój `logout` przy montowaniu.
 */
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

export function notifyUnauthorized(): void {
  onUnauthorized?.();
}
