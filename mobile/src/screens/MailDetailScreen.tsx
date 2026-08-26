/**
 * Pojedyncza wiadomość ze skrzynki - nadawca, temat, data i PEŁNA treść
 * maila. Otwarcie ekranu oznacza mail jako przeczytany (jeśli nie był) -
 * to przełącznik stanu odczytu, nie akcja biznesowa, więc mieści się
 * w zakresie "tylko podgląd" apki mobilnej.
 *
 * Treść jest dociągana ze skrzynki dopiero tutaj: w bazie na Pi leżą
 * wyłącznie metadane i krótki podgląd. Stąd wskaźnik ładowania i ścieżki
 * zapasowe - gdy backend nie odpowie albo mail zniknął ze skrzynki,
 * pokazujemy zapisany podgląd zamiast pustego ekranu.
 */
import * as React from "react";
import { Linking, ScrollView, StyleSheet, Text, View } from "react-native";
import { useRoute, type RouteProp } from "@react-navigation/native";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { useMailBody, useMailMessages, useMarkMailRead } from "@/api/hooks";
import { MailBodyFrame, canRenderMailHtml } from "@/components/MailBodyFrame";
import { Skeleton } from "@/components/Skeleton";
import { hasRemoteImages } from "@/utils/mailDocument";
import type { MailBody, MailMessage } from "@/api/types";
import type { RootStackParamList } from "@/navigation/types";

const SOURCE_LABEL: Record<string, string> = {
  allegro: "Allegro",
  allegro_lokalnie: "Allegro Lokalnie",
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

/** Treść w wersji tekstowej - wariant zapasowy i jedyny wariant natywny. */
function PlainBody({ text }: { text: string }) {
  return (
    <ScrollView style={styles.plainScroll} contentContainerStyle={styles.card}>
      <Text style={styles.body}>{text}</Text>
    </ScrollView>
  );
}

function MailBodyView({
  message,
  body,
  isLoading,
  errorMessage,
}: {
  message: MailMessage;
  body: MailBody | undefined;
  isLoading: boolean;
  errorMessage: string | null;
}) {
  if (isLoading) {
    return <Skeleton height={220} radius={radii.lg} style={{ marginTop: spacing.lg }} />;
  }

  if (errorMessage !== null) {
    return (
      <View style={styles.bodyArea}>
        <View style={styles.warning}>
          <Text style={styles.warningText}>
            Nie udało się pobrać pełnej treści ze skrzynki. {errorMessage} Poniżej zapisany
            podgląd.
          </Text>
        </View>
        <PlainBody text={message.body_preview} />
      </View>
    );
  }

  if (body?.html_body && canRenderMailHtml) {
    return (
      <View style={styles.bodyArea}>
        <MailBodyFrame html={body.html_body} />
        {hasRemoteImages(body.html_body) ? (
          <Text style={styles.imagesNote}>
            Obrazki z sieci są zablokowane - to zwykle piksele śledzące, które
            potwierdzałyby nadawcy otwarcie wiadomości.
          </Text>
        ) : null}
      </View>
    );
  }

  return (
    <View style={styles.bodyArea}>
      <PlainBody text={body?.plain_body || message.body_preview || "(wiadomość bez treści)"} />
    </View>
  );
}

export function MailDetailScreen() {
  const route = useRoute<RouteProp<RootStackParamList, "MailDetail">>();
  const { messageId } = route.params;
  const mail = useMailMessages();
  const markRead = useMarkMailRead();
  const message = mail.data?.find((m: MailMessage) => m.message_id === messageId);
  const body = useMailBody(messageId);
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
    <View style={styles.screen}>
      <View style={styles.header}>
        <View style={styles.topRow}>
          <Text style={styles.sender} numberOfLines={1}>
            {message.sender}
          </Text>
          <View style={styles.sourceTag}>
            <Text style={styles.sourceTagText}>
              {SOURCE_LABEL[message.source] ?? message.source}
            </Text>
          </View>
        </View>
        <Text style={styles.subject}>{message.subject || "(bez tematu)"}</Text>
        <Text style={styles.date}>{formatDateTime(message.received_at)}</Text>
        {message.source === "allegro_lokalnie" ? (
          <Text style={styles.readOnlyNote}>
            Allegro Lokalnie nie ma API - ORDLY tylko o tym mówi. Zamówieniem
            zarządzasz na stronie serwisu.
          </Text>
        ) : null}
      </View>

      <MailBodyView
        message={message}
        body={body.data}
        isLoading={body.isPending}
        errorMessage={
          body.isError
            ? body.error instanceof Error
              ? body.error.message
              : "Nieznany błąd."
            : null
        }
      />

      <View style={styles.footer}>
        <Text
          style={styles.link}
          onPress={() => void Linking.openURL(gmailSearchUrl(message.message_id))}
        >
          Otwórz w Gmailu (obrazki, załączniki, odpowiedź) →
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.xl,
    paddingBottom: spacing.md,
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
  bodyArea: {
    flex: 1,
    paddingHorizontal: spacing.xl,
    gap: spacing.sm,
  },
  plainScroll: {
    flex: 1,
  },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    padding: spacing.lg,
  },
  body: {
    ...typography.body,
    color: colors.textSecondary,
  },
  warning: {
    backgroundColor: colors.warningTint,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  warningText: {
    ...typography.footnote,
    color: colors.warning,
  },
  imagesNote: {
    ...typography.caption,
    color: colors.textDim,
  },
  readOnlyNote: {
    ...typography.caption,
    color: colors.warning,
    marginTop: spacing.sm,
  },
  footer: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.lg,
  },
  link: {
    ...typography.calloutSemibold,
    fontSize: 13,
    color: colors.primary,
  },
  notFound: {
    ...typography.footnote,
    color: colors.textSecondary,
    textAlign: "center",
    marginTop: spacing.xxl,
  },
});
