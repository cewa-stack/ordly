/**
 * Tekst wiadomości, który może przyjść z Allegro jako HTML.
 *
 * Komunikaty systemowe w dyskusji ("Dyskusja trwa już 14 dni...")
 * zawierają `<br>`, `<strong>` i linki, więc renderowane przez zwykły
 * `<Text>` pokazywały użytkownikowi dosłowne znaczniki. Tutaj trafiają
 * jako zagnieżdżone `<Text>`: pogrubienie jest pogrubieniem, złamanie
 * linii złamaniem, a link otwiera się w przeglądarce systemowej.
 *
 * Treść bez znaczników idzie prosto do `<Text>` - bit w bit jak dotąd,
 * ze znakami nowej linii wpisanymi przez człowieka.
 */
import * as React from "react";
import { Linking, StyleSheet, Text, type StyleProp, type TextStyle } from "react-native";

import { colors } from "@/theme/colors";
import { looksLikeHtml, parseInlineHtml } from "@/utils/html";

interface RichTextProps {
  content: string;
  style?: StyleProp<TextStyle>;
  /** Kolor linków - domyślnie akcent motywu jasnego. */
  linkColor?: string;
  numberOfLines?: number;
}

function openLink(url: string): void {
  // Brak przeglądarki / zablokowany schemat nie może wywalić ekranu
  // wątku - to tylko nieudane otwarcie linku, nie błąd aplikacji.
  void Linking.openURL(url).catch(() => undefined);
}

export function RichText({ content, style, linkColor, numberOfLines }: RichTextProps) {
  const segments = React.useMemo(
    () => (looksLikeHtml(content) ? parseInlineHtml(content) : null),
    [content]
  );

  if (segments === null) {
    return (
      <Text style={style} numberOfLines={numberOfLines}>
        {content}
      </Text>
    );
  }

  return (
    <Text style={style} numberOfLines={numberOfLines}>
      {segments.map((segment, index) => {
        const href = segment.href;
        return (
          <Text
            key={index}
            style={[
              segment.bold ? styles.bold : null,
              segment.italic ? styles.italic : null,
              href ? [styles.link, { color: linkColor ?? colors.primary }] : null,
            ]}
            onPress={href ? () => openLink(href) : undefined}
            suppressHighlighting={!href}
          >
            {segment.text}
          </Text>
        );
      })}
    </Text>
  );
}

const styles = StyleSheet.create({
  bold: {
    fontWeight: "600",
  },
  italic: {
    fontStyle: "italic",
  },
  link: {
    textDecorationLine: "underline",
  },
});
