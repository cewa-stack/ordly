/**
 * Blok szkieletowy ("skeleton") na czas ładowania - te same kształty co
 * docelowy layout, nie spinner na środku pustego ekranu
 * (docs/02_appdesign.md §7).
 */
import * as React from "react";
import { Animated, StyleSheet, View, type ViewStyle } from "react-native";

import { colors } from "@/theme/colors";
import { radii } from "@/theme/typography";

interface SkeletonProps {
  height: number;
  width?: number | `${number}%`;
  radius?: number;
  style?: ViewStyle;
}

export function Skeleton({ height, width = "100%", radius = radii.sm, style }: SkeletonProps) {
  const opacity = React.useRef(new Animated.Value(0.4)).current;

  React.useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.8, duration: 700, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.4, duration: 700, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);

  return (
    <Animated.View
      style={[
        styles.base,
        { height, width, borderRadius: radius, opacity },
        style,
      ]}
    />
  );
}

const styles = StyleSheet.create({
  base: {
    backgroundColor: colors.surfaceRaised,
  },
});
