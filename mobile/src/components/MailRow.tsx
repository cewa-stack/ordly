/**
 * Wiersz maila — nadawca + źródło (Allegro/OLX/Inne), temat, data,
 * kropka nieprzeczytanego. Dotknięcie otwiera podgląd i oznacza jako
 * przeczytany (MailDetailScreen).
 */
import * as React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { Palette } from "@/theme/colors";
import { useThemedStyles } from "@/theme/theme";
import { family, radii, spacing, typography } from "@/theme/typography";
import type { MailMessage } from "@/api/types";
import { parseApiDate } from "@/utils/format";

const SOURCE_LABEL: Record<string, string> = {
  allegro: "Allegro",
  // Krótko, bo etykieta stoi w wąskiej pastylce obok tematu. Rozwinięcie
  // ("Allegro Lokalnie - zarządzasz na stronie serwisu") jest na ekranie
  // wiadomości, gdzie jest na nie miejsce.
  allegro_lokalnie: "AL",
  olx: "OLX",
  other: "Inne",
};

function shortDateTime(iso: string): string {
  return parseApiDate(iso).toLocaleString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface MailRowProps {
  message: MailMessage;
  onPress?: () => void;
}

export function MailRow({ message, onPress }: MailRowProps) {
  const styles = useThemedStyles(createStyles);
  const unread = !message.is_read;
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
      <View style={styles.topRow}>
        {unread ? <View style={styles.dot} /> : null}
        <Text style={[styles.sender, unread && styles.senderUnread]} numberOfLines={1}>
          {message.sender}
        </Text>
        <View style={styles.sourceTag}>
          <Text style={styles.sourceTagText}>{SOURCE_LABEL[message.source] ?? message.source}</Text>
        </View>
      </View>
      <Text style={[styles.subject, unread && styles.subjectUnread]} numberOfLines={1}>
        {message.subject || "(bez tematu)"}
      </Text>
      <Text style={styles.date}>{shortDateTime(message.received_at)}</Text>
    </Pressable>
  );
}

const createStyles = (c: Palette) =>
  StyleSheet.create({
  card: {
    backgroundColor: c.card,
    borderWidth: 1,
    borderColor: c.line,
    borderRadius: radii.lg,
    padding: spacing.lg,
    marginBottom: spacing.sm,
    gap: 4,
  },
  pressed: {
    opacity: 0.85,
    backgroundColor: c.card2,
  },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: radii.full,
    backgroundColor: c.acc,
  },
  sender: {
    ...typography.footnote,
    color: c.tx2,
    flexShrink: 1,
    flexGrow: 1,
  },
  senderUnread: {
    color: c.tx,
    fontFamily: family.display,
  },
  sourceTag: {
    backgroundColor: c.card2,
    borderRadius: radii.full,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  sourceTagText: {
    ...typography.caption,
    fontSize: 9.5,
    color: c.tx3,
    textTransform: "uppercase",
  },
  subject: {
    ...typography.callout,
    color: c.tx2,
  },
  subjectUnread: {
    color: c.tx,
    fontFamily: family.sansSemibold,
  },
  date: {
    ...typography.caption,
    fontSize: 11,
    color: c.tx3,
  },
});
