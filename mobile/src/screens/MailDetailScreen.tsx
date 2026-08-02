/**
 * Podgląd maila — nadawca/temat/data/fragment treści + link do pełnej
 * wiadomości w Gmailu. Otwarcie ekranu oznacza mail jako przeczytany
 * (jeśli nie był) - to przełącznik stanu odczytu, nie akcja biznesowa,
 * więc mieści się w zakresie "tylko podgląd" apki mobilnej.
 */
import * as React from "react";
import { Linking, ScrollView, StyleSheet, Text, View } from "react-native";
import { useRoute, type RouteProp } from "@react-navigation/native";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { useMailMessages, useMarkMailRead } from "@/api/hooks";
import { Skeleton } from "@/components/Skeleton";
import type { MailMessage } from "@/api/types";
import type { RootStackParamList } from "@/navigation/types";

const SOURCE_LABEL: Record<string, string> = {
  allegro: "Allegro",
  olx: "OLX",
  other: "Inne",
};

function gmailSearchUrl(messageId: string): string {
  const cleaned = messageId.replace(/[<>]/g, "");
  return `https://mail.google.com/mail/u/0/#search/rfc822msgid:${encodeURIComponent(cleaned)}`;
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function MailDetailScreen() {
  const route = useRoute<RouteProp<RootStackParamList, "MailDetail">>();
  const { messageId } = route.params;
  const mail = useMailMessages();
  const markRead = useMarkMailRead();
  const message = mail.data?.find((m: MailMessage) => m.message_id === messageId);
  const markedRef = React.useRef(false);

  React.useEffect(() => {
    if (message && !message.is_read && !markedRef.current) {
      markedRef.current = true;
      markRead.mutate(messageId);
    }
  }, [message, messageId, markRead]);

  if (mail.isPending) {
    return (
      <View style={styles.screen}>
        <Skeleton height={140} radius={radii.lg} style={{ margin: spacing.xl }} />
      </View>
    );
  }

  if (!message) {
    return (
      <View style={styles.screen}>
        <Text style={styles.notFound}>Nie znaleziono wiadomości.</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <View style={styles.topRow}>
        <Text style={styles.sender} numberOfLines={1}>
          {message.sender}
        </Text>
        <View style={styles.sourceTag}>
          <Text style={styles.sourceTagText}>{SOURCE_LABEL[message.source] ?? message.source}</Text>
        </View>
      </View>
      <Text style={styles.subject}>{message.subject || "(bez tematu)"}</Text>
      <Text style={styles.date}>{formatDateTime(message.received_at)}</Text>

      <View style={styles.card}>
        <Text style={styles.body}>{message.body_preview}</Text>
      </View>

      <Text
        style={styles.link}
        onPress={() => void Linking.openURL(gmailSearchUrl(message.message_id))}
      >
        Otwórz pełną wiadomość w Gmail →
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.xl,
    paddingBottom: 60,
  },
  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
  },
  sender: {
    ...typography.footnote,
    color: colors.textSecondary,
    flexShrink: 1,
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
    ...typography.title2,
    color: colors.text,
    marginTop: spacing.sm,
  },
  date: {
    ...typography.caption,
    color: colors.textDim,
    marginTop: 4,
  },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    padding: spacing.lg,
    marginTop: spacing.lg,
  },
  body: {
    ...typography.body,
    color: colors.textSecondary,
  },
  link: {
    ...typography.calloutSemibold,
    fontSize: 13,
    color: colors.primary,
    marginTop: spacing.lg,
  },
  notFound: {
    ...typography.footnote,
    color: colors.textSecondary,
    textAlign: "center",
    marginTop: spacing.xxl,
  },
});
