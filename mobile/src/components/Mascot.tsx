/**
 * Maskotka ORDLY z delikatnym unoszeniem (idle-float) - używana WYŁĄCZNIE
 * w miejscach z §15.16 specyfikacji: logowanie, blokada, puste stany,
 * sukces. Nigdy na dashboardzie, listach czy w ustawieniach.
 *
 * Kazda poza niesie inne znaczenie, zeby te same puste stany nie byly
 * wizualnie monotonne w calej appce - patrz uzycia w EmptyState.tsx:
 * "orders" (czeka na zamowienia), "happy" (pusty stan = dobra wiadomosc),
 * "thinking" (szukanie nic nie znalazlo). "default" (clipboard) zostaje
 * dla logowania/ogolnych miejsc.
 *
 * Wszystkie pliki maja teraz prawdziwa przezroczystosc (tlo usuniete) -
 * renderowane bezposrednio, bez dodatkowej "plytki" w tle.
 */
import * as React from "react";
import { Animated, Easing, Image, type StyleProp, type ViewStyle } from "react-native";

export type MascotPose = "default" | "happy" | "orders" | "thinking";

const POSE_SOURCE: Record<MascotPose, number> = {
  default: require("@/assets/mascot.png") as number,
  happy: require("@/assets/mascot_happy.png") as number,
  orders: require("@/assets/mascot_orders.png") as number,
  thinking: require("@/assets/mascot_thinking.png") as number,
};

interface MascotProps {
  pose?: MascotPose;
  size?: number;
  floaty?: boolean;
  style?: StyleProp<ViewStyle>;
}

export function Mascot({ pose = "default", size = 96, floaty = true, style }: MascotProps) {
  const translateY = React.useRef(new Animated.Value(0)).current;

  React.useEffect(() => {
    if (!floaty) {
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(translateY, {
          toValue: -6,
          duration: 1900,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(translateY, {
          toValue: 0,
          duration: 1900,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [floaty, translateY]);

  return (
    <Animated.View style={[{ transform: [{ translateY }] }, style]}>
      <Image
        source={POSE_SOURCE[pose]}
        style={{ width: size, height: size }}
        resizeMode="contain"
      />
    </Animated.View>
  );
}
