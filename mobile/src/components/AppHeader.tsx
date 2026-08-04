/**
 * Nagłówek aplikacji mobilnej wg sekcji 6.1 specyfikacji:
 * powitanie + Ordi (46 px) + pigułka synchronizacji.
 *
 * Nagłówek jest WSPÓLNY dla wszystkich pięciu zakładek - nie należy do
 * żadnego ekranu z osobna. Wynika to wprost z sekcji 1: synchronizacja
 * to jedyne działanie w całej aplikacji, więc jej przycisk musi być
 * dostępny wszędzie, a nie tylko na jednym ekranie.
 *
 * Ordi siedzi w orbie z pierścieniem postępu - ten sam element
 * sygnaturowy co wskaźnik w pasku bocznym desktopu, tylko w jasnym
 * wariancie (sekcja 6.1).
 */
import * as React from "react";
import { Animated, Easing, Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { Mascot } from "@/components/Mascot";
import { ChevronRightIcon, SyncIcon } from "@/icons";
import { useSync } from "@/store/sync";

const DATE_FORMATTER = new Intl.DateTimeFormat("pl-PL", {
  weekday: "long",
  day: "numeric",
  month: "long",
});

function SyncSpinner() {
  const rotation = React.useRef(new Animated.Value(0)).current;

  React.useEffect(() => {
    // Pierścień synchronizacji: 950 ms, liniowo, w pętli (sekcja 2.6).
    const loop = Animated.loop(
      Animated.timing(rotation, {
        toValue: 1,
        duration: 950,
        easing: Easing.linear,
        useNativeDriver: true,
      })
    );
    loop.start();
    return () => loop.stop();
  }, [rotation]);

  const spin = rotation.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "360deg"],
  });

  return (
    <Animated.View style={{ transform: [{ rotate: spin }] }}>
      <SyncIcon size={16} color={colors.primary} />
    </Animated.View>
  );
}

interface AppHeaderProps {
  username: string;
}

export function AppHeader({ username }: AppHeaderProps) {
  const { pose, title, subtitle, phase, sync } = useSync();
  const popScale = React.useRef(new Animated.Value(1)).current;

  React.useEffect(() => {
    if (phase !== "success") return;
    // "Pop" po sukcesie: 1 -> 1.2 -> 1 w 550 ms (sekcja 3.2).
    Animated.sequence([
      Animated.timing(popScale, {
        toValue: 1.2,
        duration: 209,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
      Animated.timing(popScale, {
        toValue: 1,
        duration: 341,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
    ]).start();
  }, [phase, popScale]);

  return (
    <View style={styles.header}>
      <View style={styles.greetingRow}>
        <View style={styles.orb}>
          <Animated.View style={{ transform: [{ scale: popScale }] }}>
            <Mascot pose={pose} size={33} floaty={phase === "idle"} />
          </Animated.View>
        </View>
        <View style={styles.greetingCopy}>
          <Text style={styles.greeting} numberOfLines={1}>
            Cześć, {username}
          </Text>
          <Text style={styles.date}>{DATE_FORMATTER.format(new Date())}</Text>
        </View>
      </View>

      <Pressable
        onPress={sync}
        disabled={phase !== "idle"}
        accessibilityRole="button"
        accessibilityLabel="Synchronizuj z marketplace"
        style={({ pressed }) => [styles.syncPill, pressed && styles.syncPillPressed]}
      >
        {phase === "working" ? (
          <SyncSpinner />
        ) : (
          <SyncIcon size={16} color={colors.primary} />
        )}
        <View style={styles.syncCopy}>
          <Text style={styles.syncTitle}>{title}</Text>
          <Text style={styles.syncSubtitle} numberOfLines={1}>
            {subtitle}
          </Text>
        </View>
        <ChevronRightIcon size={13} color={colors.textOnIcon} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.lg,
    paddingBottom: 14,
    gap: 13,
  },
  greetingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  orb: {
    width: 46,
    height: 46,
    borderRadius: 23,
    alignItems: "center",
    justifyContent: "center",
    // Jasny odpowiednik orba z desktopu (sekcja 6.1).
    backgroundColor: "#D6EBE7",
  },
  greetingCopy: {
    flex: 1,
    minWidth: 0,
  },
  greeting: {
    ...typography.greeting,
    color: colors.text,
    letterSpacing: -0.25,
  },
  date: {
    ...typography.meta,
    color: "#6E7C77",
    marginTop: 2,
  },
  syncPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm + 2,
    paddingHorizontal: 14,
    paddingVertical: 11,
    borderRadius: 15,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: "rgba(35,43,39,0.07)",
    shadowColor: "#232B27",
    shadowOpacity: 0.1,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  syncPillPressed: {
    transform: [{ scale: 0.985 }],
  },
  syncCopy: {
    flex: 1,
    minWidth: 0,
    gap: 2,
  },
  syncTitle: {
    fontSize: 12.5,
    fontWeight: "600",
    color: colors.text,
  },
  syncSubtitle: {
    ...typography.meta,
    color: "#6E7C77",
  },
});
