/**
 * Wątek dyskusji/reklamacji — tylko do odczytu. Odpowiedzi wysyła się
 * z aplikacji desktopowej ORDLY (decyzja zakresu: mobile = podgląd + push,
 * bez akcji piszących), więc zamiast pola tekstowego jest stała notka.
 */
import * as React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useRoute, type RouteProp } from "@react-navigation/native";

import { withAlpha } from "@/theme/colors";
import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { radii, spacing, typography } from "@/theme/typography";
import { useIssueMessages, useIssues } from "@/api/hooks";
import { ErrorState } from "@/components/ErrorState";
import { RichText } from "@/components/RichText";
import { Skeleton } from "@/components/Skeleton";
import { Pill } from "@/components/Pill";
import { issueStatusLabel, issueStatusTone, parseApiDate } from "@/utils/format";
import type { Issue, IssueMessage } from "@/api/types";
import type { RootStackParamList } from "@/navigation/types";

/**
 * Ton zgloszenia w kolorach AKTYWNEJ atmosfery. Funkcja, nie stala -
 * paleta zmienia sie w trakcie dzialania aplikacji (sekcja 11).
 */
function toneColors(tone: string, c: Palette): { color: string; tint: string } {
  switch (tone) {
    case "ok":
      return { color: c.acc, tint: c.accDim };
    case "warn":
      return { color: c.amber, tint: withAlpha(c.amber, 0.14) };
    default:
      return { color: c.coral, tint: withAlpha(c.coral, 0.14) };
  }
}

function formatDateTime(iso: string): string {
  return parseApiDate(iso).toLocaleString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function IssueDetailScreen() {
  const styles = useThemedStyles(createStyles);
  const { c } = useTheme();
  const route = useRoute<RouteProp<RootStackParamList, "IssueDetail">>();
  const { issueId } = route.params;
  // Lista jest zwykle już w cache z DiscussionsScreen - to tylko dociąga
  // wątek wiadomości, który żyje pod osobnym zapytaniem.
  const issues = useIssues();
  const messages = useIssueMessages(issueId);
  const issue = issues.data?.find((i: Issue) => i.external_id === issueId);
  const threadRef = React.useRef<ScrollView>(null);

  if (messages.isPending) {
    return (
      <View style={styles.screen}>
        <Skeleton height={100} radius={radii.lg} style={{ margin: spacing.xl }} />
      </View>
    );
  }

  if (messages.isError) {
    return (
      <View style={styles.screen}>
        <ErrorState onRetry={() => messages.refetch()} />
      </View>
    );
  }

  const tone = issue ? issueStatusTone(issue.status) : "warn";

  return (
    <View style={styles.screen}>
      {issue ? (
        <View style={styles.headerCard}>
          <View style={styles.badgeRow}>
            <Pill
              label={issue.type === "CLAIM" ? "Reklamacja" : "Dyskusja"}
              color={c.acc}
              tint={c.accDim}
            />
            <Pill
              label={issueStatusLabel(issue.status)}
              {...toneColors(tone, c)}
            />
          </View>
          <Text style={styles.subject}>{issue.subject ?? "Bez tematu"}</Text>
          <Text style={styles.meta}>
            Zamówienie #{issue.order_external_id} · {issue.buyer_login}
          </Text>
        </View>
      ) : null}

      {/* Konwencja komunikatora: najstarsza wiadomość u góry, najnowsza
          na dole - a otwarcie wątku ma pokazywać właśnie tę najnowszą,
          bez ręcznego przewijania przez całą historię. Backend oddaje
          wątek już posortowany rosnąco (IssuesService.get_thread). */}
      <ScrollView
        ref={threadRef}
        contentContainerStyle={styles.thread}
        onContentSizeChange={() => threadRef.current?.scrollToEnd({ animated: false })}
      >
        {(messages.data ?? []).map((message: IssueMessage) => {
          const isSeller = message.author_role === "SELLER";
          return (
            <View key={message.id} style={[styles.bubbleRow, isSeller && styles.bubbleRowSeller]}>
              <View style={[styles.bubble, isSeller ? styles.bubbleSeller : styles.bubbleBuyer]}>
                <RichText content={message.text} style={styles.bubbleText} />
                <Text style={styles.bubbleMeta}>
                  {isSeller ? "Ty" : message.author_login} · {formatDateTime(message.created_at)}
                </Text>
              </View>
            </View>
          );
        })}
      </ScrollView>

      <View style={styles.footer}>
        <Text style={styles.footerText}>Odpowiedz na laptopie w aplikacji ORDLY Desktop.</Text>
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
  headerCard: {
    borderBottomWidth: 1,
    borderBottomColor: c.line,
    padding: spacing.xl,
  },
  badgeRow: {
    flexDirection: "row",
    gap: spacing.xs,
  },
  subject: {
    ...typography.title2,
    color: c.tx,
    marginTop: spacing.sm,
  },
  meta: {
    ...typography.footnote,
    color: c.tx2,
    marginTop: 2,
  },
  thread: {
    padding: spacing.xl,
    gap: spacing.sm,
    flexGrow: 1,
  },
  bubbleRow: {
    flexDirection: "row",
    justifyContent: "flex-start",
  },
  bubbleRowSeller: {
    justifyContent: "flex-end",
  },
  bubble: {
    maxWidth: "82%",
    borderRadius: radii.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  bubbleBuyer: {
    backgroundColor: c.card,
    borderWidth: 1,
    borderColor: c.line,
  },
  bubbleSeller: {
    backgroundColor: c.accDim,
  },
  bubbleText: {
    ...typography.callout,
    color: c.tx,
  },
  bubbleMeta: {
    ...typography.caption,
    fontSize: 10,
    color: c.tx3,
    marginTop: 4,
  },
  footer: {
    borderTopWidth: 1,
    borderTopColor: c.line,
    padding: spacing.lg,
  },
  footerText: {
    ...typography.footnote,
    color: c.tx3,
    textAlign: "center",
  },
});
