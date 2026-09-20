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

import { withAlpha } from "@/theme/colors";
import type { Palette } from "@/theme/colors";
import { useThemedStyles } from "@/theme/theme";
import { radii, spacing, typography } from "@/theme/typography";
import { useMailBody, useMailMessages, useMarkMailRead } from "@/api/hooks";
import { MailBodyFrame, canRenderMailHtml } from "@/components/MailBodyFrame";
import { Skeleton } from "@/components/Skeleton";
import { parseApiDate } from "@/utils/format";
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
  return parseApiDate(iso).toLocaleString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Treść w wersji tekstowej - wariant zapasowy i jedyny wariant natywny. */
function PlainBody({ text }: { text: string }) {
  const styles = useThemedStyles(createStyles);
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
  const styles = useThemedStyles(createStyles);
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
  const styles = useThemedStyles(createStyles);
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

const createStyles = (c: Palette) =>
  StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: c.bg,
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
    color: c.tx2,
    flexShrink: 1,
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
    ...typography.title2,
    color: c.tx,
    marginTop: spacing.sm,
  },
  date: {
    ...typography.caption,
    color: c.tx3,
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
    backgroundColor: c.card,
    borderWidth: 1,
    borderColor: c.line,
    borderRadius: radii.lg,
    padding: spacing.lg,
  },
  body: {
    ...typography.body,
    color: c.tx2,
  },
  warning: {
    backgroundColor: withAlpha(c.amber, 0.14),
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  warningText: {
    ...typography.footnote,
    color: c.amber,
  },
  imagesNote: {
    ...typography.caption,
    color: c.tx3,
  },
  readOnlyNote: {
    ...typography.caption,
    color: c.amber,
    marginTop: spacing.sm,
  },
  footer: {
    borderTopWidth: 1,
    borderTopColor: c.line,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.lg,
  },
  link: {
    ...typography.calloutSemibold,
    fontSize: 13,
    color: c.acc,
  },
  notFound: {
    ...typography.footnote,
    color: c.tx2,
    textAlign: "center",
    marginTop: spacing.xxl,
  },
});
