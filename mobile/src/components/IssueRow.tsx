/**
 * Wiersz dyskusji/reklamacji — typ (pastylka primary), temat, kupujący +
 * zamówienie, status (pastylka kolorowa), data ostatniej wiadomości.
 * Dotknięcie otwiera wątek tylko do odczytu (IssueDetailScreen).
 */
import * as React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { withAlpha } from "@/theme/colors";
import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { radii, spacing, typography } from "@/theme/typography";
import { ChevronRightIcon } from "@/icons";
import type { Issue } from "@/api/types";
import { issueStatusLabel, issueStatusTone, parseApiDate } from "@/utils/format";
import { Pill } from "./Pill";

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

function shortDate(iso: string): string {
  return parseApiDate(iso).toLocaleDateString("pl-PL", { day: "numeric", month: "short" });
}

interface IssueRowProps {
  issue: Issue;
  onPress?: () => void;
}

export function IssueRow({ issue, onPress }: IssueRowProps) {
  const styles = useThemedStyles(createStyles);
  const { c } = useTheme();
  const tone = issueStatusTone(issue.status);
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
      <View style={styles.topRow}>
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
      <Text style={styles.subject} numberOfLines={1}>
        {issue.subject ?? "Bez tematu"}
      </Text>
      <View style={styles.bottomRow}>
        <Text style={styles.meta} numberOfLines={1}>
          {issue.buyer_login} · zamówienie #{issue.order_external_id}
        </Text>
        <View style={styles.trailing}>
          {issue.last_message_at ? (
            <Text style={styles.date}>{shortDate(issue.last_message_at)}</Text>
          ) : null}
          <ChevronRightIcon size={16} color={c.tx3} />
        </View>
      </View>
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
    gap: spacing.xs,
  },
  pressed: {
    opacity: 0.85,
    backgroundColor: c.card2,
  },
  topRow: {
    flexDirection: "row",
    gap: spacing.xs,
  },
  subject: {
    ...typography.calloutSemibold,
    fontSize: 15,
    color: c.tx,
    marginTop: 2,
  },
  bottomRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
  },
  meta: {
    ...typography.footnote,
    color: c.tx2,
    flexShrink: 1,
  },
  trailing: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  date: {
    ...typography.caption,
    fontSize: 11,
    color: c.tx3,
  },
});
