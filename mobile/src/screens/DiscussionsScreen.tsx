/**
 * Dyskusje i reklamacje — podgląd tylko do odczytu. Odpowiedzi wysyła się
 * z aplikacji desktopowej ORDLY (decyzja zakresu: mobile = podgląd + push,
 * bez akcji piszących).
 */
import * as React from "react";
import { FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useQueryClient } from "@tanstack/react-query";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { useIssues } from "@/api/hooks";
import { IssueRow } from "@/components/IssueRow";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { TabHeading } from "@/components/TabHeading";
import { ListEndNote } from "@/components/ListEndNote";
import { Skeleton } from "@/components/Skeleton";
import type { Issue } from "@/api/types";
import type { RootStackParamList } from "@/navigation/types";

export function DiscussionsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const issues = useIssues();
  const queryClient = useQueryClient();

  async function onRefresh() {
    await queryClient.invalidateQueries({ queryKey: ["issues"] });
  }

  function renderItem({ item }: { item: Issue }) {
    return (
      <IssueRow
        issue={item}
        onPress={() => navigation.navigate("IssueDetail", { issueId: item.external_id })}
      />
    );
  }

  return (
    <View style={styles.screen}>
      <TabHeading title="Dyskusje" />

      {issues.isPending ? (
        <View style={styles.listPadding}>
          <Skeleton height={96} radius={radii.lg} style={{ marginBottom: spacing.sm }} />
          <Skeleton height={96} radius={radii.lg} />
        </View>
      ) : issues.isError ? (
        <ErrorState onRetry={() => issues.refetch()} />
      ) : (
        <FlatList
          data={issues.data ?? []}
          keyExtractor={(item) => item.external_id}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={issues.isRefetching}
              onRefresh={onRefresh}
              tintColor={colors.primary}
            />
          }
          ListFooterComponent={
            (issues.data ?? []).length > 0 ? (
              <ListEndNote text="Odpowiadać można tylko z desktopu - tutaj widzisz, co czeka." />
            ) : null
          }
          ListEmptyComponent={
            <EmptyState
              mascotPose="happy"
              title="Brak otwartych spraw"
              description="Zero dyskusji i reklamacji do obsłużenia — spokojnie."
            />
          }
        />
      )}
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
    paddingTop: spacing.lg,
    paddingBottom: spacing.md,
  },
  title: {
    ...typography.title1,
    color: colors.text,
  },
  listPadding: {
    paddingHorizontal: spacing.xl,
  },
  listContent: {
    paddingHorizontal: spacing.xl,
    paddingBottom: 96,
  },
});
