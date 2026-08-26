/**
 * Treść maila w izolowanej ramce - tylko w kompilacji web (PWA).
 *
 * Mail to pełny dokument HTML z własnymi stylami. Wstawiony do drzewa
 * aplikacji rozjechałby jej układ, a pozbawiony stylów przestałby być
 * czytelny - dlatego dostaje własny dokument w `<iframe>`, dokładnie tak
 * jak w aplikacji desktopowej.
 *
 * Dlaczego `<iframe>`, a nie `react-native-webview`: ORDLY Mobile jest na
 * telefonie używany jako PWA w Safari (patrz `src/push/webPush.ts` -
 * powiadomienia idą przez Web Push, nie Expo Push), a `react-native-webview`
 * NIE ma implementacji na web. Ramka przeglądarki jest tu narzędziem
 * właściwym, nie obejściem.
 *
 * W kompilacji natywnej (Expo Go / build) ten komponent świadomie nie
 * renderuje nic - ekran wiadomości pokazuje wtedy wersję tekstową maila,
 * którą backend dostarcza zawsze (`plain_body`).
 */
import * as React from "react";
import { Platform } from "react-native";

import { buildMailDocument } from "@/utils/mailDocument";

/** Czy ta platforma potrafi wyrenderować pełny dokument HTML maila. */
export const canRenderMailHtml = Platform.OS === "web";

interface MailBodyFrameProps {
  html: string;
}

export function MailBodyFrame({ html }: MailBodyFrameProps) {
  if (!canRenderMailHtml) return null;

  // `createElement` zamiast JSX: `iframe` to element DOM, którego nie ma
  // w słowniku komponentów React Native - w tym pliku sięgamy po niego
  // świadomie i tylko na webie (guard wyżej).
  return React.createElement("iframe", {
    title: "Treść wiadomości",
    // Bez `allow-scripts` i bez `allow-same-origin`: żaden skrypt z maila
    // się nie wykona, a `allow-popups` pozwala tylko na to, żeby kliknięty
    // link otworzył się w nowej karcie.
    sandbox: "allow-popups allow-popups-to-escape-sandbox",
    srcDoc: buildMailDocument(html),
    style: {
      flex: 1,
      width: "100%",
      border: "none",
      borderRadius: 12,
      backgroundColor: "#FFFFFF",
    },
  });
}
