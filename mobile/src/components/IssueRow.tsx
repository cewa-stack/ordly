/**
 * Wiersz dyskusji/reklamacji — typ (pastylka primary), temat, kupujący +
 * zamówienie, status (pastylka kolorowa), data ostatniej wiadomości.
 * Dotknięcie otwiera wątek tylko do odczytu (IssueDetailScreen).
 */
import * as React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { ChevronRightIcon } from "@/icons";
import type { Issue } from "@/api/types";
import { issueStatusLabel, issueStatusTone } from "@/utils/format";
import { Pill } from "./Pill";

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

function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pl-PL", { day: "numeric", month: "short" });
}

interface IssueRowProps {
  issue: Issue;
  onPress?: () => void;
}

export function IssueRow({ issue, onPress }: IssueRowProps) {
  const tone = issueStatusTone(issue.status);
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
      <View style={styles.topRow}>
        <Pill
          label={issue.type === "CLAIM" ? "Reklamacja" : "Dyskusja"}
          color={colors.primary}
          tint={colors.primaryTint}
        />
        <Pill label={issueStatusLabel(issue.status)} color={TONE_COLOR[tone]} tint={TONE_TINT[tone]} />
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
          <ChevronRightIcon size={16} color={colors.textDim} />
        </View>
      </View>
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
    gap: spacing.xs,
  },
  pressed: {
    opacity: 0.85,
    backgroundColor: colors.surfaceRaised,
  },
  topRow: {
    flexDirection: "row",
    gap: spacing.xs,
  },
  subject: {
    ...typography.calloutSemibold,
    fontSize: 15,
    color: colors.text,
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
    color: colors.textSecondary,
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
    color: colors.textDim,
  },
});
