import { QueryClient } from "@tanstack/react-query";

/**
 * Wspolna konfiguracja zapytan.
 *
 * `retry: 1` zamiast domyslnych 3 prob: ORDLY rozmawia z jednym,
 * wlasnym Raspberry Pi przez Tailscale - gdy Pi nie odpowiada, trzy
 * proby z narastajacym odstepem tylko wydluzaja czas do pokazania
 * uzytkownikowi konkretnego bledu.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: true,
      staleTime: 15_000,
    },
  },
});
