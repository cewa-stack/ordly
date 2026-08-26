/**
 * Wątek dyskusji/reklamacji — tylko do odczytu. Odpowiedzi wysyła się
 * z aplikacji desktopowej ORDLY (decyzja zakresu: mobile = podgląd + push,
 * bez akcji piszących), więc zamiast pola tekstowego jest stała notka.
 */
import * as React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useRoute, type RouteProp } from "@react-navigation/native";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { useIssueMessages, useIssues } from "@/api/hooks";
import { ErrorState } from "@/components/ErrorState";
import { RichText } from "@/components/RichText";
import { Skeleton } from "@/components/Skeleton";
import { Pill } from "@/components/Pill";
import { issueStatusLabel, issueStatusTone } from "@/utils/format";
import type { Issue, IssueMessage } from "@/api/types";
import type { RootStackParamList } from "@/navigation/types";

const TONE_COLOR: Record<string, string> = {
  ok: colors.success,
  warn: colors.warning,
  crit: colors.danger,
};
const TONE_TINT: Record<string, string> = {
  ok: colors.successTint,
  warn: colors.warningTint,
  crit: colors.dangerTint,
};

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function IssueDetailScreen() {
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
              color={colors.primary}
              tint={colors.primaryTint}
            />
            <Pill
              label={issueStatusLabel(issue.status)}
              color={TONE_COLOR[tone]}
              tint={TONE_TINT[tone]}
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

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  headerCard: {
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    padding: spacing.xl,
  },
  badgeRow: {
    flexDirection: "row",
    gap: spacing.xs,
  },
  subject: {
    ...typography.title2,
    color: colors.text,
    marginTop: spacing.sm,
  },
  meta: {
    ...typography.footnote,
    color: colors.textSecondary,
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
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  bubbleSeller: {
    backgroundColor: colors.primaryTint,
  },
  bubbleText: {
    ...typography.callout,
    color: colors.text,
  },
  bubbleMeta: {
    ...typography.caption,
    fontSize: 10,
    color: colors.textDim,
    marginTop: 4,
  },
  footer: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    padding: spacing.lg,
  },
  footerText: {
    ...typography.footnote,
    color: colors.textDim,
    textAlign: "center",
  },
});
