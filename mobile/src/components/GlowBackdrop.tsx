/**
 * Miękka poświata za maskotką (splash/login/lock) - trzy współśrodkowe
 * koła o malejącej nieprzezroczystości udają radialny gradient bez
 * potrzeby dodatkowej biblioteki blur/canvas.
 */
import * as React from "react";
import { StyleSheet, View } from "react-native";

import { colors } from "@/theme/colors";

export function GlowBackdrop() {
  return (
    <View style={styles.wrap} pointerEvents="none">
      <View style={[styles.ring, styles.ring1]} />
      <View style={[styles.ring, styles.ring2]} />
      <View style={[styles.ring, styles.ring3]} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "flex-start",
  },
  ring: {
    position: "absolute",
    top: -60,
    borderRadius: 999,
    backgroundColor: colors.primary,
  },
  ring1: { width: 260, height: 260, opacity: 0.05 },
  ring2: { width: 180, height: 180, top: -20, opacity: 0.07 },
  ring3: { width: 110, height: 110, top: 15, opacity: 0.09 },
});
