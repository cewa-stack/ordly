/**
 * List przewozowy - tlo ekranow blokady, logowania i wlaczania Face ID
 * (wariant C z przegladu 22.09, zastapil trzy kola "poswiaty").
 *
 * Sklep jest "zapakowany", dopoki go nie otworzysz: etykieta z kodem
 * kreskowym z dzisiejszej daty, pola nadawcy i odbiorcy, pieczatka, a
 * rogi trzymaja dwa kawalki tasmy. `opened` odkleja tasmy i prostuje
 * etykiete - to moment odblokowania.
 *
 * Geometria jest opisana w ukladzie 370 x 230 (wycinek makiety 390 px
 * od punktu 10,40), a komponent skaluje ja do `width`. Warstwy, ktore
 * sie ruszaja, sa OSOBNYMI `Animated.View` z wlasnym SVG - animowanie
 * atrybutow wewnatrz SVG nie dziala jednakowo na webie i natywnie,
 * a transformacje widokow tak.
 *
 * ZADNYCH `id` w SVG (jak w Ordlaku) - komponent potrafi byc zamontowany
 * dwa razy naraz przy przejsciu miedzy ekranami.
 */
import * as React from "react";
import { Animated, Easing, View } from "react-native";
import Svg, { Circle, G, Line, Path, Rect, Text as SvgText } from "react-native-svg";

import { useTheme } from "@/theme/theme";
import { family } from "@/theme/typography";

const VIEW_W = 370;
const VIEW_H = 230;
/** Poczatek wycinka w ukladzie makiety - wszystkie liczby nizej sa w nim. */
const OX = 10;
const OY = 40;

const TAPE_W = 73;
const TAPE_H = 24;
/** Zeby na koncach, jak po oderwaniu tasmy od rolki. */
const TAPE_PATH = "M0 1H70l3 5.5-3 5.5 3 5.5-3 5.5H0l3-5.5-3-5.5 3-5.5-3-5.5Z";

const pad = (n: number) => String(n).padStart(2, "0");

/** Kod kreskowy wyliczony z daty - ten sam przez caly dzien, inny jutro. */
function barcode(seed: number): { x: number; w: number; h: number }[] {
  let state = seed;
  const next = () => {
    state = (state * 1103515245 + 12345) % 2147483648;
    return state / 2147483648;
  };
  const widths = [0.8, 1.2, 1.8, 2.6];
  const gaps = [0.9, 1.4, 2.1];
  const bars: { x: number; w: number; h: number }[] = [];
  let x = 104;
  while (x < 236) {
    const w = widths[Math.floor(next() * widths.length)];
    const guard = bars.length < 2 || x > 231;
    bars.push({ x, w, h: guard ? 34 : 30 });
    x += w + gaps[Math.floor(next() * gaps.length)];
  }
  return bars;
}

function useClock(): Date {
  const [now, setNow] = React.useState(() => new Date());
  React.useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(timer);
  }, []);
  return now;
}

interface WaybillProps {
  width: number;
  /** Login z sesji - trafia w pole ODBIORCA. */
  recipient?: string | null;
  /** Odklejone tasmy i wyprostowana etykieta. */
  opened?: boolean;
}

export function Waybill({ width, recipient, opened = false }: WaybillProps) {
  const { c, reduceMotion } = useTheme();
  const s = width / VIEW_W;
  const height = VIEW_H * s;
  const now = useClock();

  const dd = pad(now.getDate());
  const mo = pad(now.getMonth() + 1);
  const yy = now.getFullYear();
  const hh = pad(now.getHours());
  const mm = pad(now.getMinutes());
  const bars = React.useMemo(() => barcode(yy * 10000 + Number(mo) * 100 + Number(dd)), [yy, mo, dd]);

  const progress = React.useRef(new Animated.Value(opened ? 1 : 0)).current;
  React.useEffect(() => {
    Animated.timing(progress, {
      toValue: opened ? 1 : 0,
      duration: reduceMotion ? 0 : opened ? 820 : 0,
      easing: Easing.linear,
      useNativeDriver: true,
    }).start();
  }, [opened, progress, reduceMotion]);

  // Tasma A schodzi pierwsza, B chwile po niej - jak zdzierana reka.
  const tapeA = progress.interpolate({
    inputRange: [0, 0.85],
    outputRange: [0, 1],
    extrapolate: "clamp",
    easing: Easing.in(Easing.cubic),
  });
  const tapeB = progress.interpolate({
    inputRange: [0.15, 1],
    outputRange: [0, 1],
    extrapolate: "clamp",
    easing: Easing.in(Easing.cubic),
  });
  const labelTurn = progress.interpolate({
    inputRange: [0, 1],
    outputRange: ["-3deg", "0deg"],
    easing: Easing.out(Easing.cubic),
  });

  const tape = (
    cx: number,
    cy: number,
    anim: Animated.AnimatedInterpolation<number>,
    rest: number,
    away: { x: number; y: number; rot: number }
  ) => (
    <Animated.View
      pointerEvents="none"
      style={{
        position: "absolute",
        left: (cx - TAPE_W / 2 - OX) * s,
        top: (cy - TAPE_H / 2 - OY) * s,
        width: TAPE_W * s,
        height: TAPE_H * s,
        opacity: anim.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }),
        transform: [
          { translateX: anim.interpolate({ inputRange: [0, 1], outputRange: [0, away.x * s] }) },
          { translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [0, away.y * s] }) },
          {
            rotate: anim.interpolate({
              inputRange: [0, 1],
              outputRange: [`${rest}deg`, `${away.rot}deg`],
            }),
          },
        ],
      }}
    >
      <Svg width={TAPE_W * s} height={TAPE_H * s} viewBox={`0 0 ${TAPE_W} ${TAPE_H}`}>
        <Path d={TAPE_PATH} fill={c.tape} stroke={c.tapeEdge} strokeWidth={1} />
        <SvgText
          x={35}
          y={14.6}
          fill={c.tapeInk}
          fontFamily={family.monoBold}
          fontSize={7}
          letterSpacing={2.1}
          textAnchor="middle"
        >
          ORDLY
        </SvgText>
      </Svg>
    </Animated.View>
  );

  const small = { fontFamily: family.mono, fontSize: 6.8, letterSpacing: 0.7, fill: c.tx3 };
  const value = { fontFamily: family.mono, fontSize: 9, fill: c.tx };
  const big = { fontFamily: family.display, fontSize: 11, fill: c.tx };
  const viewBox = `${OX} ${OY} ${VIEW_W} ${VIEW_H}`;

  return (
    <View style={{ width, height }} pointerEvents="none" accessible={false}>
      {/* znaczniki drukarskie - nie ruszaja sie, etykieta tak */}
      <Svg width={width} height={height} viewBox={viewBox} style={{ position: "absolute" }}>
        <G stroke={c.tx3} strokeWidth={0.9} fill="none" opacity={0.55}>
          <Path d="M24 70v-10h10M366 70v-10h-10M24 236v10h10M366 236v10h-10" />
          <Circle cx={366} cy={262} r={4.5} />
          <Path d="M366 255v14M359 262h14" />
        </G>
      </Svg>

      <Animated.View
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          width,
          height,
          transformOrigin: `${(195 - OX) * s}px ${(150 - OY) * s}px`,
          transform: [{ rotate: labelTurn }],
        }}
      >
        <Svg width={width} height={height} viewBox={viewBox}>
          <Rect x={44} y={82} width={310} height={150} rx={6} fill={c.shadow} opacity={0.3} />
          <Rect x={40} y={76} width={310} height={150} rx={6} fill={c.paper} stroke={c.line2} />
          <Line x1={92} y1={84} x2={92} y2={218} stroke={c.tx3} strokeDasharray="2 3" opacity={0.6} />
          <Circle cx={66} cy={94} r={4} fill={c.bg} stroke={c.line2} />
          <SvgText
            x={0}
            y={0}
            transform="translate(70 206) rotate(-90)"
            fill={c.acc}
            fontFamily={family.monoBold}
            fontSize={10}
            letterSpacing={3.8}
          >
            ORDLY
          </SvgText>

          <SvgText x={104} y={94} {...small}>
            LIST PRZEWOZOWY
          </SvgText>
          <SvgText x={338} y={94} textAnchor="end" {...small}>
            {`Nr ORD-${hh}${mm}`}
          </SvgText>
          <Line x1={104} y1={100} x2={338} y2={100} stroke={c.line2} />

          <G fill={c.tx} opacity={0.88}>
            {bars.map((bar) => (
              <Rect key={bar.x} x={bar.x} y={108} width={bar.w} height={bar.h} />
            ))}
          </G>
          <SvgText
            x={104}
            y={150}
            fill={c.tx2}
            fontFamily={family.mono}
            fontSize={7}
            letterSpacing={1.26}
          >
            {`${dd}${mo} ${yy} ${hh}${mm} 1`}
          </SvgText>

          <SvgText x={262} y={114} {...small}>
            DATA
          </SvgText>
          <SvgText x={262} y={125} {...value}>
            {`${dd}.${mo}.${yy}`}
          </SvgText>
          <SvgText x={262} y={140} {...small}>
            GODZ.
          </SvgText>
          <SvgText x={262} y={151} {...value}>
            {`${hh}:${mm}`}
          </SvgText>

          <Line x1={104} y1={159} x2={338} y2={159} stroke={c.line2} />
          <SvgText x={104} y={172} {...small}>
            NADAWCA
          </SvgText>
          <SvgText x={104} y={186} {...big}>
            ORDLY
          </SvgText>
          <SvgText x={180} y={172} {...small}>
            ODBIORCA
          </SvgText>
          <SvgText x={180} y={186} {...big}>
            {(recipient || "Ty").slice(0, 12)}
          </SvgText>
          <SvgText x={262} y={172} {...small}>
            ZAWARTOŚĆ
          </SvgText>
          <SvgText x={262} y={186} {...big}>
            Twój sklep
          </SvgText>
          <Line x1={104} y1={196} x2={338} y2={196} stroke={c.line2} />
          <SvgText x={104} y={210} {...small}>
            NIE ZGINAĆ · OTWIERAĆ FACE ID
          </SvgText>

          <G transform="rotate(-9 292 232)" opacity={0.82}>
            <Rect x={242} y={217} width={100} height={30} rx={4} fill="none" stroke={c.acc} strokeWidth={1.6} />
            <SvgText
              x={292}
              y={230}
              textAnchor="middle"
              fill={c.acc}
              fontFamily={family.monoBold}
              fontSize={7.6}
              letterSpacing={1.06}
            >
              ZAPIECZĘTOWANE
            </SvgText>
            <SvgText
              x={292}
              y={241}
              textAnchor="middle"
              fill={c.acc}
              fontFamily={family.mono}
              fontSize={6.8}
              letterSpacing={0.54}
            >
              {`${dd}.${mo} · ${hh}:${mm}`}
            </SvgText>
          </G>
        </Svg>
      </Animated.View>

      {tape(52, 82, tapeA, -38, { x: -80, y: -70, rot: -75 })}
      {tape(338, 80, tapeB, 36, { x: 80, y: -70, rot: 72 })}
    </View>
  );
}

/** Proporcje etykiety - ekrany licza z nich, ile miejsca potrzebuje. */
export const WAYBILL_ASPECT = VIEW_H / VIEW_W;
