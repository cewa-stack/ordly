/**
 * Wiersz maila — nadawca + źródło (Allegro/OLX/Inne), temat, data,
 * kropka nieprzeczytanego. Dotknięcie otwiera podgląd i oznacza jako
 * przeczytany (MailDetailScreen).
 */
import * as React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import type { MailMessage } from "@/api/types";

const SOURCE_LABEL: Record<string, string> = {
  allegro: "Allegro",
  olx: "OLX",
  other: "Inne",
};

function shortDateTime(iso: string): string {
  return new Date(iso).toLocaleString("pl-PL", {
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

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    padding: spacing.lg,
    marginBottom: spacing.sm,
    gap: 4,
  },
  pressed: {
    opacity: 0.85,
    backgroundColor: colors.surfaceRaised,
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
    backgroundColor: colors.primary,
  },
  sender: {
    ...typography.footnote,
    color: colors.textSecondary,
    flexShrink: 1,
    flexGrow: 1,
  },
  senderUnread: {
    color: colors.text,
    fontWeight: "700",
  },
  sourceTag: {
    backgroundColor: colors.surfaceRaised,
    borderRadius: radii.full,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  sourceTagText: {
    ...typography.caption,
    fontSize: 9.5,
    color: colors.textDim,
    textTransform: "uppercase",
  },
  subject: {
    ...typography.callout,
    color: colors.textSecondary,
  },
  subjectUnread: {
    color: colors.text,
    fontWeight: "600",
  },
  date: {
    ...typography.caption,
    fontSize: 11,
    color: colors.textDim,
  },
});
