/**
 * Koniec listy wg sekcji 7.4 specyfikacji.
 *
 * To nie jest ozdoba ani wypełniacz. Gdy użytkownik dojedzie na telefonie
 * do końca listy, aplikacja mówi mu WPROST, gdzie wykonać akcję - bo
 * mobile świadomie jej nie ma (sekcja 1: "Desktop robi. Telefon
 * pokazuje."). Bez tego użytkownik szuka przycisku, którego nigdy nie
 * będzie, i uznaje aplikację za niedokończoną.
 *
 * Uzasadnienie do zakomunikowania: nikt nie powinien zatwierdzać zwrotu
 * jedną ręką, stojąc w magazynie.
 */
import * as React from "react";
import { StyleSheet, Text, View } from "react-native";

import { colors } from "@/theme/colors";
import { spacing, typography } from "@/theme/typography";
import { Mascot } from "@/components/Mascot";

interface ListEndNoteProps {
  /** Pełne zdanie kończące listę - patrz przykłady w sekcji 7.4. */
  text: string;
}

export function ListEndNote({ text }: ListEndNoteProps) {
  return (
    <View style={styles.row}>
      <Mascot pose="default" size={48} floaty={false} style={styles.mascot} />
      <Text style={styles.text}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 13,
    paddingTop: spacing.xl,
    paddingBottom: spacing.sm,
    paddingHorizontal: 6,
  },
  mascot: {
    opacity: 0.85,
  },
  text: {
    flex: 1,
    fontSize: 11.5,
    lineHeight: 18,
    color: colors.textSecondary,
  },
});
