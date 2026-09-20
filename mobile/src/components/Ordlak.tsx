/**
 * Ordlak - maskotka ORDLY dla React Native (sekcja 6 instrukcji
 * "Nokturn"). Ta sama geometria i te same czasy co na desktopie.
 *
 * Trzy rzeczy, o ktorych latwo zapomniec przy przenoszeniu z CSS:
 *
 * 1. `react-native-svg` nie zna `overflow:visible` - cala tresc musi
 *    miescic sie w `0 0 128 128`. Wersja ponizej sie miesci.
 * 2. `transform-box: fill-box` nie istnieje. Punkty obrotu podaje sie
 *    JAWNIE: figura (64, 113), oczy (60, 70), antena (60, 46) - w
 *    ukladzie PRZED przesunieciem. Ponizej sa przeliczone na piksele
 *    przez `transformOrigin`.
 * 3. Przesuniecie -8,4 / -0,5 idzie jako `<G translate>`, nie jako styl.
 *
 * ODSTEPSTWO OD INSTRUKCJI (swiadome): instrukcja mowi
 * `react-native-reanimated`. Projekt go nie ma, a dolozenie go wymaga
 * wtyczki Babela i przebudowy natywnej - dla szesciu petli o stalym
 * czasie wbudowane `Animated` wystarcza i dziala tez na webie (ORDLY
 * mobile chodzi takze jako PWA). Czasy i krzywe sa te same.
 *
 * Ruch jest zlozony z petli 0->1, z ktorych kazda wlasciwosc jest
 * INTERPOLOWANA - to najbardziej doslowne odwzorowanie klatek
 * kluczowych z CSS, jakie da sie zrobic bez reanimated.
 */
import * as React from "react";
import { Animated, Easing, View, type StyleProp, type ViewStyle } from "react-native";
import Svg, { Circle, Ellipse, G, Line, Path, Rect, Text as SvgText } from "react-native-svg";

import { useTheme } from "@/theme/theme";

export type OrdlakState = "idle" | "sync" | "think" | "happy" | "alert" | "sleep";

/** Przesuniecie z sekcji 6: 64 - 72.41 oraz 64 - 64.5. */
const SHIFT_X = -8.4;
const SHIFT_Y = -0.5;
const VIEW = 128;

/** Punkty obrotu w ukladzie PO przesunieciu. */
const ORIGIN_FIGURE = { x: 64 + SHIFT_X, y: 113 + SHIFT_Y };
const ORIGIN_EYES = { x: 60 + SHIFT_X, y: 70 + SHIFT_Y };
const ORIGIN_ANT = { x: 60 + SHIFT_X, y: 46 + SHIFT_Y };

/** Ramka figury: 92,81 x 97 jednostek - podstawa przeliczen procentow. */
const FIGURE_W = 92.81;
const FIGURE_H = 97;

interface OrdlakProps {
  state?: OrdlakState;
  size?: number;
  style?: StyleProp<ViewStyle>;
}

/** Petla 0->1 o stalym czasie. Zwraca wartosc do interpolacji. */
function useLoop(duration: number, active: boolean, easing = Easing.linear): Animated.Value {
  const value = React.useRef(new Animated.Value(0)).current;
  React.useEffect(() => {
    value.setValue(0);
    if (!active) return;
    const loop = Animated.loop(
      Animated.timing(value, {
        toValue: 1,
        duration,
        easing,
        useNativeDriver: true,
      })
    );
    loop.start();
    return () => loop.stop();
  }, [value, duration, active, easing]);
  return value;
}

/** Warstwa SVG na calej powierzchni - wszystkie uzywaja tego samego viewBox. */
function Layer({
  children,
  style,
  size,
}: {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  size: number;
}) {
  return (
    <Animated.View
      pointerEvents="none"
      style={[{ position: "absolute", left: 0, top: 0, width: size, height: size }, style]}
    >
      <Svg width={size} height={size} viewBox={`0 0 ${VIEW} ${VIEW}`}>
        <G translateX={SHIFT_X} translateY={SHIFT_Y}>
          {children}
        </G>
      </Svg>
    </Animated.View>
  );
}

export function Ordlak({ state = "idle", size = 40, style }: OrdlakProps) {
  const { c, reduceMotion } = useTheme();
  const scale = size / VIEW;

  // W atmosferze dziennej maskotka dostaje glebsze odcienie - jasny teal
  // na bieli sie rozmywa (sekcja 6).
  const isDay = c.bg === "#EFF3F0";
  let skin = isDay ? "#35B3AA" : c.acc;
  let skinDark = isDay ? "#166F6E" : "#3EAAAF";
  if (state === "alert") {
    skin = isDay ? "#EE6B47" : "#FF8563";
    skinDark = isDay ? "#B4462E" : "#D8563A";
  } else if (state === "sleep") {
    skin = "#3C6A66";
    skinDark = "#2C4F4C";
  }
  const eyeFill = isDay ? "#0B2B29" : "#062120";
  const boardFill = isDay ? "#12332F" : "#0B1A18";

  // `prefers-reduced-motion`: Ordlak zostaje w pozie spoczynku. Stany
  // nadal zmieniaja kolor i mimike - znika wylacznie ruch (sekcja 14).
  const moving = !reduceMotion;

  const bob = useLoop(state === "sleep" ? 5400 : 3600, moving && (state === "idle" || state === "sleep"));
  const blink = useLoop(6000, moving && state === "idle");
  const wave = useLoop(1500, moving && state === "sync");
  const scan = useLoop(1900, moving && state === "sync");
  const breathe = useLoop(1200, moving && state === "sync");
  const lean = useLoop(2600, moving && state === "think");
  const antwig = useLoop(1100, moving && state === "think");
  const dots = useLoop(1400, moving && state === "think");
  const hop = useLoop(1250, moving && state === "happy");
  const shake = useLoop(700, moving && state === "alert");
  const bang = useLoop(1000, moving && state === "alert");
  const zzz = useLoop(2600, moving && state === "sleep");

  // ---------------------------------------------------- ruch figury
  // Tablica transformacji budowana warunkowo - RN nie przyjmuje `undefined`
  // wsrod wpisow, wiec skladamy ja tylko z tych, ktore stan naprawde wnosi.
  const figureTransform: NonNullable<ViewStyle["transform"]> = [];
  if (state === "idle" || state === "sleep") {
    figureTransform.push({
      translateY: bob.interpolate({
        inputRange: [0, 0.5, 1],
        outputRange: [0, -0.035 * FIGURE_H * scale, 0],
      }),
    } as never);
  } else if (state === "think") {
    figureTransform.push(
      {
        rotate: lean.interpolate({
          inputRange: [0, 0.5, 1],
          outputRange: ["-2.5deg", "1.5deg", "-2.5deg"],
        }),
      } as never,
      {
        translateY: lean.interpolate({
          inputRange: [0, 0.5, 1],
          outputRange: [0, -0.02 * FIGURE_H * scale, 0],
        }),
      } as never
    );
  } else if (state === "happy") {
    figureTransform.push(
      {
        translateY: hop.interpolate({
          inputRange: [0, 0.28, 0.46, 0.62, 1],
          outputRange: [
            0,
            -0.11 * FIGURE_H * scale,
            0,
            -0.04 * FIGURE_H * scale,
            0,
          ],
        }),
      } as never,
      {
        scaleY: hop.interpolate({
          inputRange: [0, 0.28, 0.46, 0.62, 1],
          outputRange: [1, 1.04, 0.94, 1, 1],
        }),
      } as never
    );
  } else if (state === "alert") {
    figureTransform.push({
      translateX: shake.interpolate({
        inputRange: [0, 0.18, 0.38, 0.58, 0.78, 1],
        outputRange: [
          0,
          -0.025 * FIGURE_W * scale,
          0.025 * FIGURE_W * scale,
          -0.015 * FIGURE_W * scale,
          0.015 * FIGURE_W * scale,
          0,
        ],
      }),
    } as never);
  }

  // ------------------------------------------------------ ruch oczu
  const eyesTransform: NonNullable<ViewStyle["transform"]> = [];
  if (state === "idle") {
    eyesTransform.push({
      scaleY: blink.interpolate({
        inputRange: [0, 0.92, 0.95, 1],
        outputRange: [1, 1, 0.08, 1],
      }),
    } as never);
  } else if (state === "sync") {
    eyesTransform.push({
      translateX: scan.interpolate({
        inputRange: [0, 0.5, 1],
        outputRange: [-0.07 * 38 * scale, 0.07 * 38 * scale, -0.07 * 38 * scale],
      }),
    } as never);
  } else if (state === "think") {
    eyesTransform.push(
      { translateX: -0.04 * 38 * scale } as never,
      { translateY: -0.06 * 20 * scale } as never
    );
  } else if (state === "alert") {
    eyesTransform.push({ scale: 1.14 } as never);
  }

  const originPx = (o: { x: number; y: number }) =>
    `${o.x * scale}px ${o.y * scale}px` as unknown as ViewStyle["transformOrigin"];

  /**
   * Fale i kropki dziela jedna petle, ale kazda ma wlasne przesuniecie
   * fazowe. Zamiast trzech osobnych petli (ktore rozjechalyby sie po
   * kilku minutach) kazda czyta te sama wartosc z przesunietym zakresem.
   */
  const phased = (
    value: Animated.Value,
    delay: number,
    period: number,
    frames: [number, number][]
  ) => {
    const shift = delay / period;
    const points: number[] = [];
    const values: number[] = [];
    // Przepisuje klatki dwa razy - raz przesuniete w tyl, raz w przod -
    // zeby zakres wejsciowy pokryl pelne 0..1 bez dziury na zawinieciu.
    for (const offset of [-1, 0, 1]) {
      for (const [at, v] of frames) {
        const x = at + shift + offset;
        if (x >= -0.001 && x <= 1.001) {
          points.push(Math.min(1, Math.max(0, x)));
          values.push(v);
        }
      }
    }
    if (points.length < 2 || points[0] > 0) {
      points.unshift(0);
      values.unshift(frames[frames.length - 1][1]);
    }
    if (points[points.length - 1] < 1) {
      points.push(1);
      values.push(values[0]);
    }
    // Zakres wejsciowy musi byc scisle rosnacy.
    for (let i = 1; i < points.length; i += 1) {
      if (points[i] <= points[i - 1]) points[i] = points[i - 1] + 0.0001;
    }
    return value.interpolate({ inputRange: points, outputRange: values });
  };

  const WAVE_FRAMES: [number, number][] = [
    [0, 0],
    [0.12, 0.95],
    [0.72, 0],
    [1, 0],
  ];
  const DOT_FRAMES: [number, number][] = [
    [0, 0.18],
    [0.3, 1],
    [0.6, 0.18],
    [1, 0.18],
  ];

  return (
    <View
      accessibilityRole="image"
      // Stan NIE jest w etykiecie (sekcja 14) - czytnik ekranu nie ma
      // powtarzac "Ordlak synchronizuje" przy kazdym odswiezeniu.
      accessibilityLabel="Ordlak"
      style={[{ width: size, height: size }, style]}
    >
      {/* cien - nie rusza sie razem z figura */}
      <Layer size={size}>
        <Ellipse cx="60" cy="118" rx="29" ry="4.6" fill="#000" opacity={isDay ? 0.13 : 0.3} />
      </Layer>

      {/* figura */}
      <Animated.View
        pointerEvents="none"
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          width: size,
          height: size,
          transformOrigin: originPx(ORIGIN_FIGURE),
          transform: figureTransform as never,
        }}
      >
        <Svg width={size} height={size} viewBox={`0 0 ${VIEW} ${VIEW}`}>
          <G translateX={SHIFT_X} translateY={SHIFT_Y}>
            <Rect x="36" y="101" width="16" height="12" rx="6" fill={skinDark} />
            <Rect x="64" y="101" width="16" height="12" rx="6" fill={skinDark} />
            <Rect x="26" y="44" width="68" height="64" rx="28" fill={skin} />
            {state === "alert" ? (
              <Path
                d="M52 88q8-6 16 0"
                stroke={eyeFill}
                strokeWidth={3.4}
                strokeLinecap="round"
                fill="none"
              />
            ) : (
              <Path
                d="M52 86q8 6 16 0"
                stroke={eyeFill}
                strokeWidth={3.4}
                strokeLinecap="round"
                fill="none"
                opacity={state === "sleep" ? 0.4 : 1}
              />
            )}
            <G rotation={7} origin="101, 81">
              <Rect
                x="86"
                y="62"
                width="30"
                height="38"
                rx="5"
                fill={boardFill}
                stroke={skinDark}
                strokeWidth={2.6}
              />
              <Rect x="95" y="57" width="12" height="8" rx="3" fill={skinDark} />
              <Line x1="92" y1="76" x2="110" y2="76" stroke={skin} strokeWidth={2.6} strokeLinecap="round" opacity={0.5} />
              <Line x1="92" y1="84" x2="110" y2="84" stroke={skin} strokeWidth={2.6} strokeLinecap="round" opacity={0.5} />
              <Line x1="92" y1="92" x2="104" y2="92" stroke={skin} strokeWidth={2.6} strokeLinecap="round" opacity={0.5} />
            </G>
          </G>
        </Svg>

        {/* antena - wlasny punkt obrotu u podstawy lodygi */}
        <Animated.View
          pointerEvents="none"
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            width: size,
            height: size,
            transformOrigin: originPx(ORIGIN_ANT),
            transform:
              state === "think"
                ? ([
                    {
                      rotate: antwig.interpolate({
                        inputRange: [0, 0.5, 1],
                        outputRange: ["-13deg", "13deg", "-13deg"],
                      }),
                    },
                  ] as never)
                : undefined,
          }}
        >
          <Svg width={size} height={size} viewBox={`0 0 ${VIEW} ${VIEW}`}>
            <G translateX={SHIFT_X} translateY={SHIFT_Y}>
              <Line x1="60" y1="46" x2="60" y2="27" stroke={skinDark} strokeWidth={3.4} strokeLinecap="round" />
            </G>
          </Svg>
          {/*
            Zarowka anteny ma WLASNA warstwe, a nie animowany atrybut
            `opacity` na <Circle>. Wartosc z petli jest sterowana
            natywnie (`useNativeDriver`), a podpiecie takiej wartosci pod
            zwykly prop react-native-svg wywala sie w czasie dzialania
            ("Attempting to run JS driven animation on animated node that
            has been moved to native"). Krycie warstwy jest natywne i
            bezpieczne.
          */}
          <Layer
            size={size}
            style={
              state === "sync"
                ? {
                    opacity: breathe.interpolate({
                      inputRange: [0, 0.5, 1],
                      outputRange: [0.35, 1, 0.35],
                    }),
                  }
                : undefined
            }
          >
            <Circle cx="60" cy="22" r="6" fill={skin} />
          </Layer>
        </Animated.View>

        {/* oczy */}
        <Animated.View
          pointerEvents="none"
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            width: size,
            height: size,
            transformOrigin: originPx(ORIGIN_EYES),
            transform: eyesTransform as never,
          }}
        >
          <Svg width={size} height={size} viewBox={`0 0 ${VIEW} ${VIEW}`}>
            <G translateX={SHIFT_X} translateY={SHIFT_Y}>
              {state === "happy" ? (
                <>
                  <Path d="M42 72q6-8 12 0" stroke={eyeFill} strokeWidth={4.4} strokeLinecap="round" fill="none" />
                  <Path d="M66 72q6-8 12 0" stroke={eyeFill} strokeWidth={4.4} strokeLinecap="round" fill="none" />
                </>
              ) : state === "sleep" ? (
                <>
                  <Path d="M42 69q6 6 12 0" stroke={eyeFill} strokeWidth={4.4} strokeLinecap="round" fill="none" />
                  <Path d="M66 69q6 6 12 0" stroke={eyeFill} strokeWidth={4.4} strokeLinecap="round" fill="none" />
                </>
              ) : (
                <>
                  <Ellipse cx="48" cy="70" rx="6" ry="7" fill={eyeFill} />
                  <Ellipse cx="72" cy="70" rx="6" ry="7" fill={eyeFill} />
                  <Circle cx="50.2" cy="66.8" r="2" fill="#EAF3EF" opacity={0.92} />
                  <Circle cx="74.2" cy="66.8" r="2" fill="#EAF3EF" opacity={0.92} />
                </>
              )}
            </G>
          </Svg>
        </Animated.View>
      </Animated.View>

      {/* ------------------------------------------------- sygnaly */}
      {state === "sync" && (
        <>
          <Layer size={size} style={{ opacity: phased(wave, 0, 1.5, WAVE_FRAMES) }}>
            <Path d="M51.8 16.3A10 10 0 0 1 68.2 16.3" stroke={c.acc} strokeWidth={3.4} fill="none" strokeLinecap="round" />
          </Layer>
          <Layer size={size} style={{ opacity: phased(wave, 0.18, 1.5, WAVE_FRAMES) }}>
            <Path d="M47.7 13.4A15 15 0 0 1 72.3 13.4" stroke={c.acc} strokeWidth={3.4} fill="none" strokeLinecap="round" />
          </Layer>
          <Layer size={size} style={{ opacity: phased(wave, 0.36, 1.5, WAVE_FRAMES) }}>
            <Path d="M43.6 10.5A20 20 0 0 1 76.4 10.5" stroke={c.acc} strokeWidth={3.4} fill="none" strokeLinecap="round" />
          </Layer>
        </>
      )}

      {state === "think" && (
        <>
          <Layer size={size} style={{ opacity: phased(dots, 0, 1.4, DOT_FRAMES) }}>
            <Circle cx="98" cy="36" r="3" fill={c.acc} />
          </Layer>
          <Layer size={size} style={{ opacity: phased(dots, 0.18, 1.4, DOT_FRAMES) }}>
            <Circle cx="108" cy="27" r="3.8" fill={c.acc} />
          </Layer>
          <Layer size={size} style={{ opacity: phased(dots, 0.36, 1.4, DOT_FRAMES) }}>
            <Circle cx="119" cy="17" r="4.6" fill={c.acc} />
          </Layer>
        </>
      )}

      {state === "alert" && (
        <Layer
          size={size}
          style={{
            opacity: bang.interpolate({
              inputRange: [0, 0.5, 1],
              outputRange: [0.35, 1, 0.35],
            }),
          }}
        >
          <Path d="M100 20v14" stroke={c.coral} strokeWidth={5} strokeLinecap="round" />
          <Path d="M100 42v.5" stroke={c.coral} strokeWidth={5} strokeLinecap="round" />
        </Layer>
      )}

      {state === "happy" && (
        <Layer
          size={size}
          style={{
            opacity: hop.interpolate({
              inputRange: [0, 0.4, 1],
              outputRange: [0, 1, 0],
            }),
          }}
        >
          <Path
            d="M100 25 102.5 31.5 109 34 102.5 36.5 100 43 97.5 36.5 91 34 97.5 31.5Z"
            fill={c.acc}
          />
          <Path
            d="M26 35.5 27.8 40.2 32.5 42 27.8 43.8 26 48.5 24.2 43.8 19.5 42 24.2 40.2Z"
            fill={c.acc}
          />
        </Layer>
      )}

      {state === "sleep" && (
        <Layer
          size={size}
          style={{
            opacity: zzz.interpolate({
              inputRange: [0, 0.3, 1],
              outputRange: [0, 1, 0],
            }),
            transform: [
              {
                translateY: zzz.interpolate({
                  inputRange: [0, 0.3, 1],
                  outputRange: [4 * scale, 0, -12 * scale],
                }),
              },
            ] as never,
          }}
        >
          <SvgText x="96" y="36" fontSize="15" fontWeight="700" fill={c.acc}>
            z
          </SvgText>
          <SvgText x="108" y="22" fontSize="20" fontWeight="700" fill={c.acc}>
            z
          </SvgText>
        </Layer>
      )}
    </View>
  );
}
