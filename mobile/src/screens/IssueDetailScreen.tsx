/**
 * Wątek dyskusji/reklamacji z polem odpowiedzi.
 *
 * Odpowiedź to jedyna akcja pisząca na telefonie poza synchronizacją.
 * Widzi ją kupujący i nie da się jej cofnąć, więc przed wysłaniem jest
 * okno potwierdzenia z początkiem treści - tak samo jak przy działaniach
 * Ordlaka. Szablony są te same co na desktopie (edytuje się je tam),
 * a login i numer przesyłki podstawia `fillTemplate`.
 */
import * as React from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useRoute, type RouteProp } from "@react-navigation/native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { withAlpha } from "@/theme/colors";
import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { fonts, radii, spacing, typography } from "@/theme/typography";
import {
  useIssueMessages,
  useIssues,
  useOrder,
  useReplyTemplates,
  useReplyToIssue,
} from "@/api/hooks";
import { ApiError } from "@/api/client";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ErrorState } from "@/components/ErrorState";
import { RichText } from "@/components/RichText";
import { Skeleton } from "@/components/Skeleton";
import { Pill } from "@/components/Pill";
import { ArrowUpIcon } from "@/icons";
import { issueStatusLabel, issueStatusTone, parseApiDate } from "@/utils/format";
import { fillTemplate, hasTemplateGap } from "@/utils/replyTemplate";
import type { Issue, IssueMessage, ReplyTemplate } from "@/api/types";
import type { RootStackParamList } from "@/navigation/types";

/** Tyle treści pokazuje okno potwierdzenia - reszta jest w polu nad nim. */
const PREVIEW_CHARS = 140;

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
  // Natywny nagłówek stosu ma 44 pt nad marginesem bezpiecznym. Na webie
  // (PWA) klawiaturę obsługuje przeglądarka i przesunięcie nie gra roli.
  const headerHeight = useSafeAreaInsets().top + 44;

  const canReply = Boolean(issue?.chat_active);
  const templates = useReplyTemplates(canReply);
  // Numer przesyłki do szablonu „Wysłane”. Jedno zapytanie na otwarty
  // wątek, i tylko gdy da się jeszcze odpowiedzieć.
  const order = useOrder(canReply ? issue?.order_external_id : undefined);
  const reply = useReplyToIssue(issueId);
  const [draft, setDraft] = React.useState("");
  // Treść w oknie potwierdzenia jest zapamiętana osobno: okno gaśnie
  // jeszcze chwilę po wysłaniu, a pole już jest puste - bez tego opis
  // w trakcie zamykania pokazywał puste „”.
  const [confirm, setConfirm] = React.useState({ visible: false, text: "" });
  const gap = hasTemplateGap(draft);
  const canSend = canReply && draft.trim().length > 0 && !gap && !reply.isPending;

  const send = () => {
    reply.mutate(confirm.text, {
      onSuccess: () => {
        setDraft("");
        setConfirm((prev) => ({ ...prev, visible: false }));
      },
      onError: () => setConfirm((prev) => ({ ...prev, visible: false })),
    });
  };

  if (messages.isPending) {
    return (
      <View style={styles.screen}>
        <Skeleton height={100} radius={radii.lg} style={{ margin: spacing.xl }} />
      </View>
    );
  }

  if (messages.isError && !messages.data) {
    return (
      <View style={styles.screen}>
        <ErrorState onRetry={() => messages.refetch()} />
      </View>
    );
  }

  const tone = issue ? issueStatusTone(issue.status) : "warn";
  const preview =
    confirm.text.length > PREVIEW_CHARS
      ? `${confirm.text.slice(0, PREVIEW_CHARS).trimEnd()}…`
      : confirm.text;
  // Pole rośnie z treścią (szablon ma kilka akapitów), ale najwyżej do
  // sześciu wierszy - dalej przewija się w środku. Natywny iOS rośnie sam.
  const inputLines = Math.min(6, Math.max(1, draft.split("\n").length));

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={headerHeight}
    >
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

      {canReply ? (
        <View style={styles.footer}>
          {templates.data && templates.data.length > 0 ? (
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.templates}
              keyboardShouldPersistTaps="handled"
            >
              {templates.data.map((template: ReplyTemplate) => (
                <Pressable
                  key={template.id}
                  // Czekamy na zamówienie, żeby nie wstawić luki tam, gdzie
                  // numer przesyłki za chwilę będzie znany.
                  disabled={template.body.includes("{numer_przesylki}") && order.isLoading}
                  onPress={() =>
                    setDraft(
                      fillTemplate(template.body, {
                        login: issue?.buyer_login ?? "",
                        orderId: issue?.order_external_id ?? "",
                        trackingNumber: order.data?.tracking_number ?? null,
                      })
                    )
                  }
                  accessibilityRole="button"
                  accessibilityLabel={`Wstaw szablon: ${template.title}`}
                  style={({ pressed }) => [styles.chip, pressed && styles.pressed]}
                >
                  <Text style={styles.chipText} numberOfLines={1}>
                    {template.title}
                  </Text>
                </Pressable>
              ))}
            </ScrollView>
          ) : null}

          <View style={styles.composer}>
            <TextInput
              value={draft}
              onChangeText={setDraft}
              placeholder="Napisz odpowiedź…"
              placeholderTextColor={c.tx3}
              editable={!reply.isPending}
              multiline
              numberOfLines={inputLines}
              style={styles.input}
            />
            <Pressable
              onPress={() => setConfirm({ visible: true, text: draft.trim() })}
              disabled={!canSend}
              accessibilityRole="button"
              accessibilityLabel="Wyślij odpowiedź"
              style={({ pressed }) => [
                styles.send,
                !canSend && styles.sendDisabled,
                pressed && styles.pressed,
              ]}
            >
              {reply.isPending ? (
                <ActivityIndicator size="small" color={c.onAcc} />
              ) : (
                <ArrowUpIcon size={16} color={c.onAcc} />
              )}
            </Pressable>
          </View>

          {gap ? (
            <Text style={[styles.note, { color: c.coral }]}>
              Uzupełnij pole w ‹ › przed wysłaniem — zamówienie nie ma jeszcze numeru przesyłki.
            </Text>
          ) : reply.isError ? (
            <Text style={[styles.note, { color: c.coral }]}>
              {reply.error instanceof ApiError
                ? reply.error.message
                : "Allegro nie przyjęło odpowiedzi. Spróbuj ponownie za chwilę."}
            </Text>
          ) : reply.isSuccess && draft.length === 0 ? (
            <Text style={[styles.note, { color: c.acc }]}>Odpowiedź wysłana.</Text>
          ) : null}
        </View>
      ) : issue ? (
        <View style={styles.footer}>
          <Text style={styles.footerText}>Wątek zamknięty przez Allegro — nie da się już odpowiedzieć.</Text>
        </View>
      ) : null}

      <ConfirmDialog
        visible={confirm.visible}
        title="Wysłać odpowiedź?"
        description={`Do ${issue?.buyer_login ?? "kupującego"}: „${preview}”. Kupujący zobaczy ją od razu na Allegro — nie da się jej cofnąć.`}
        confirmLabel="Wyślij"
        busy={reply.isPending}
        onConfirm={send}
        onCancel={() => setConfirm((prev) => ({ ...prev, visible: false }))}
      />
    </KeyboardAvoidingView>
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
    paddingVertical: spacing.md,
    gap: spacing.sm,
  },
  footerText: {
    ...typography.footnote,
    color: c.tx3,
    textAlign: "center",
    paddingHorizontal: spacing.lg,
  },
  templates: {
    gap: 6,
    paddingHorizontal: spacing.lg,
  },
  chip: {
    borderRadius: radii.full,
    borderWidth: 1,
    borderColor: c.line2,
    paddingVertical: 6,
    paddingHorizontal: 11,
  },
  chipText: {
    ...fonts.caption,
    fontSize: 11.5,
    color: c.tx2,
  },
  composer: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: spacing.sm,
    borderRadius: 23,
    backgroundColor: c.card,
    borderWidth: 1,
    borderColor: c.line,
    marginHorizontal: spacing.lg,
    paddingLeft: 16,
    paddingRight: 5,
    paddingVertical: 5,
  },
  input: {
    flex: 1,
    minWidth: 0,
    maxHeight: 120,
    ...fonts.body,
    fontSize: 13.5,
    color: c.tx,
    paddingTop: 9,
    paddingBottom: 9,
    paddingHorizontal: 0,
  },
  send: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: c.acc,
    alignItems: "center",
    justifyContent: "center",
  },
  sendDisabled: {
    opacity: 0.4,
  },
  pressed: {
    opacity: 0.85,
  },
  note: {
    ...typography.caption,
    paddingHorizontal: spacing.lg,
  },
});
