/**
 * Wejście z powiadomienia w konkretny rekord (akcja „Pokaż" z sekcji 04
 * koncepcji push, wymóg 9.2 pkt 3 specyfikacji UI).
 *
 * Dwie drogi, obie muszą działać:
 *
 * 1. **Aplikacja już otwarta** - service worker wysyła `postMessage`,
 *    ten hook go łapie i nawiguje bez przeładowania.
 * 2. **Zimny start** - okna nie było, więc service worker zrobił
 *    `openWindow(url)`; adres czytamy raz przy montowaniu i czyścimy,
 *    żeby odświeżenie strony nie wrzucało użytkownika w ten sam rekord.
 */
import * as React from "react";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import {
  consumeInitialPushTarget,
  subscribeToPushNavigation,
  type PushTarget,
} from "@/push/pushNavigation";
import type { RootStackParamList } from "./types";

type Navigation = NativeStackNavigationProp<RootStackParamList>;

export function usePushDeepLinks(enabled: boolean): void {
  const navigation = useNavigation<Navigation>();

  const go = React.useCallback(
    (target: PushTarget) => {
      switch (target.screen) {
        case "OrderDetail":
          navigation.navigate("OrderDetail", target.params);
          return;
        case "StockItem":
          navigation.navigate("StockItem", target.params);
          return;
        case "IssueDetail":
          navigation.navigate("IssueDetail", target.params);
          return;
        case "MailDetail":
          navigation.navigate("MailDetail", target.params);
          return;
        case "Settings":
          navigation.navigate("Settings");
          return;
        case "MainTab":
          navigation.navigate("Main", { screen: target.params.tab });
          return;
      }
    },
    [navigation]
  );

  React.useEffect(() => {
    if (!enabled) return;

    const initial = consumeInitialPushTarget();
    if (initial) go(initial);

    return subscribeToPushNavigation(go);
  }, [enabled, go]);
}
