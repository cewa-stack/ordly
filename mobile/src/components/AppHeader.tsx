/**
 * Nagłówek ekranu mobilnego (sekcja 11 instrukcji "Nokturn").
 *
 *   padding: 6px 20px 14px
 *   nadtytuł  - mono 9,5 px wersalikami, `tx3`
 *   tytuł     - Bricolage 700 / 24 px, akcentowane słowo w `acc`
 *   awatar    - 38 px z inicjałami, mono 12 px, po prawej
 *
 * ZMIANA WOBEC POPRZEDNIEJ WERSJI: zniknęła pigułka synchronizacji.
 * Synchronizacja nie przepadła - przeniosła się na kartę Ordlaka na
 * ekranie Start (dotknięcie karty uruchamia cykl), a listy mają
 * pociągnięcie w dół. Nagłówek ma nieść, GDZIE jesteś, nie mieścić
 * jedynego przycisku aplikacji.
 *
 * Awatar prowadzi do Ustawień - to jedyne wejście do powiadomień push,
 * Face ID i wylogowania.
 */
import * as React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useNavigation } from "@react-navigation/native";

import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { fonts, spacing } from "@/theme/typography";

interface AppHeaderProps {
  /** Nadtytuł wersalikami, np. "PONIEDZIAŁEK · 22 WRZEŚNIA". */
  eyebrow: string;
  /** Tytuł ekranu. */
  title: string;
  /**
   * Słowo z tytułu, które świeci akcentem. Musi być fragmentem `title` -
   * inaczej nie zostanie podświetlone (i o to chodzi: nie doklejamy
   * słów, których w tytule nie ma).
   */
  accent?: string;
  initials: string;
}

export function AppHeader({ eyebrow, title, accent, initials }: AppHeaderProps) {
  const styles = useThemedStyles(createStyles);
  const { c } = useTheme();
  const navigation = useNavigation();

  // Tytuł rozbity na trzy części, żeby akcent nie wymagał osobnego pola
  // i nie dało się podświetlić czegoś, czego w tytule nie ma.
  const index = accent ? title.indexOf(accent) : -1;
  const before = index >= 0 ? title.slice(0, index) : title;
  const middle = index >= 0 ? accent! : "";
  const after = index >= 0 ? title.slice(index + accent!.length) : "";

  return (
    <View style={styles.header}>
      <View style={styles.copy}>
        <Text style={styles.eyebrow} numberOfLines={1}>
          {eyebrow}
        </Text>
        <Text style={styles.title} numberOfLines={1}>
          {before}
          {middle ? <Text style={{ color: c.acc }}>{middle}</Text> : null}
          {after}
        </Text>
      </View>

      <Pressable
        onPress={() => navigation.navigate("Settings")}
        accessibilityRole="button"
        accessibilityLabel="Ustawienia i powiadomienia"
        hitSlop={8}
        style={({ pressed }) => [styles.avatar, pressed && styles.pressed]}
      >
        <Text style={styles.initials}>{initials}</Text>
      </Pressable>
    </View>
  );
}

const createStyles = (c: Palette) =>
  StyleSheet.create({
    header: {
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.md,
      paddingTop: 6,
      paddingHorizontal: spacing.xl,
      paddingBottom: 14,
    },
    copy: {
      flex: 1,
      minWidth: 0,
    },
    eyebrow: {
      ...fonts.eyebrow,
      color: c.tx3,
    },
    title: {
      ...fonts.screenTitle,
      color: c.tx,
      marginTop: 4,
    },
    avatar: {
      width: 38,
      height: 38,
      borderRadius: 19,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: c.card,
      borderWidth: 1,
      borderColor: c.line2,
    },
    pressed: {
      opacity: 0.75,
    },
    initials: {
      ...fonts.mono,
      fontSize: 12,
      color: c.tx2,
    },
  });
