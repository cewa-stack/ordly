/**
 * Zestaw ikon ORDLY Mobile - linia (stroke), nie wypełnienie, 1:1 z
 * zatwierdzonym mockupem (docs/02_appdesign.md §4). Celowo NIE korzysta z
 * biblioteki ikon "z automatu" (Feather/Ionicons) - każdy kształt był
 * częścią decyzji projektowej, nie placeholderem.
 *
 * Wszystkie ikony renderują się identycznie: `stroke-width: 2`,
 * `round` linecap/linejoin, kolor przez prop `color` (domyślnie
 * `colors.muted`), rozmiar przez prop `size` (domyślnie 20).
 */
import * as React from "react";
import Svg, { Circle, Path, Rect } from "react-native-svg";

import { colors } from "@/theme/colors";

export interface IconProps {
  size?: number;
  color?: string;
}

const defaults = { size: 20, color: colors.textSecondary } as const;

/** Dzwonek - powiadomienia (Start, top bar). */
export function BellIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Path
        d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M13.7 21a2 2 0 01-3.4 0"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Ciężarówka - "do wysłania". */
export function TruckIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Rect x={1} y={7} width={15} height={10} rx={1} stroke={color} strokeWidth={2} />
      <Path
        d="M16 10h3.5L22 13.5V17h-6"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Circle cx={6} cy={19} r={1.6} stroke={color} strokeWidth={2} />
      <Circle cx={17.5} cy={19} r={1.6} stroke={color} strokeWidth={2} />
    </Svg>
  );
}

/**
 * Poziom niski (bateria) - "niski stan". Renderowana identycznie jak
 * `TruckIcon` (bez tła, sam kontur) - patrz zasada w 02_appdesign.md §4.
 */
export function LowLevelIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Rect x={2} y={7} width={17} height={10} rx={2.5} stroke={color} strokeWidth={2} />
      <Path d="M21 10v4" stroke={color} strokeWidth={2} strokeLinecap="round" />
      <Rect x={4.5} y={9.5} width={3} height={5} rx={1} fill={color} />
    </Svg>
  );
}

/** Strzałka w górę - trend sprzedaży. */
export function TrendUpIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Path
        d="M5 12l7-7 7 7M12 19V5"
        stroke={color}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Dom - zakładka Start. */
export function HomeIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Path
        d="M3 11l9-8 9 8M5 10v10h14V10"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Paragon - zakładka Zamówienia. */
export function ReceiptIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Path
        d="M4 7h16M6 7l1 13h10l1-13M9 7V5a3 3 0 016 0v2"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Skrzynka - zakładka Magazyn. */
export function BoxIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Path
        d="M3 8l9-5 9 5-9 5-9-5zM3 8v8l9 5 9-5V8"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Lupa - wyszukiwarka. */
export function SearchIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Circle cx={11} cy={11} r={7} stroke={color} strokeWidth={2} />
      <Path d="M21 21l-4.3-4.3" stroke={color} strokeWidth={2} strokeLinecap="round" />
    </Svg>
  );
}

/** Chevron w prawo - linki "wszystkie →", "raport →". */
export function ChevronRightIcon({
  size = defaults.size,
  color = defaults.color,
}: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Path
        d="M9 6l6 6-6 6"
        stroke={color}
        strokeWidth={2.4}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Plus - dodaj produkt / akcja twórcza. */
export function PlusIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Path
        d="M12 5v14M5 12h14"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Zębatka - ustawienia. */
export function GearIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Circle cx={12} cy={12} r={3.2} stroke={color} strokeWidth={2} />
      <Path
        d="M12 3v2.4M12 18.6V21M21 12h-2.4M5.4 12H3M18.4 5.6l-1.7 1.7M7.3 16.7l-1.7 1.7M18.4 18.4l-1.7-1.7M7.3 7.3L5.6 5.6"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
      />
    </Svg>
  );
}

/** X - zamknij / wyczyść. */
export function CloseIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Path
        d="M6 6l12 12M18 6L6 18"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Odśwież (refresh-cw) - synchronizacja z marketplace. */
export function SyncIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Path
        d="M21 8a9 9 0 00-15.5-3.4L3 7M3 7V3m0 4h4M3 16a9 9 0 0015.5 3.4L21 17m0 0v4m0-4h-4"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Ptaszek - węzeł ukończony na osi statusów, potwierdzenia. */
export function CheckIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Path
        d="M4 12.5l5 5L20 6.5"
        stroke={color}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Trójkąt ostrzegawczy - alerty magazynu ("Wymaga uwagi"). */
export function AlertIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Path
        d="M12 3.5L22 20H2L12 3.5z"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path d="M12 10v4.5" stroke={color} strokeWidth={2} strokeLinecap="round" />
      <Circle cx={12} cy={17.2} r={0.6} fill={color} stroke={color} strokeWidth={1} />
    </Svg>
  );
}

/** Twarz w ramce (Face ID) - odblokowanie biometryczne. */
export function FaceIdIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Path
        d="M7 3H5a2 2 0 00-2 2v2M17 3h2a2 2 0 012 2v2M7 21H5a2 2 0 01-2-2v-2M17 21h2a2 2 0 002-2v-2"
        stroke={color}
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path d="M9 9.5v1.5M15 9.5v1.5" stroke={color} strokeWidth={1.8} strokeLinecap="round" />
      <Path d="M9.5 15a3.5 3.5 0 005 0" stroke={color} strokeWidth={1.8} strokeLinecap="round" />
    </Svg>
  );
}

/** Osoba (kontur) - pole loginu. */
export function UserIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Circle cx={12} cy={8} r={3.6} stroke={color} strokeWidth={1.8} />
      <Path
        d="M4.5 20c1.4-3.6 4.4-5.5 7.5-5.5s6.1 1.9 7.5 5.5"
        stroke={color}
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Kłódka - pole hasła. */
export function LockIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Rect x={4} y={10} width={16} height={10} rx={2.5} stroke={color} strokeWidth={1.8} />
      <Path d="M8 10V7a4 4 0 018 0v3" stroke={color} strokeWidth={1.8} strokeLinecap="round" />
    </Svg>
  );
}

/** Serwer (dwa poziome pasy) - pole adresu API. */
export function ServerIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Rect x={3} y={4} width={18} height={7} rx={2} stroke={color} strokeWidth={1.7} />
      <Rect x={3} y={13} width={18} height={7} rx={2} stroke={color} strokeWidth={1.7} />
      <Path d="M7 7.5h.01M7 16.5h.01" stroke={color} strokeWidth={2.2} strokeLinecap="round" />
    </Svg>
  );
}

/** Otwarte oko - "pokaż hasło". */
export function EyeIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Path
        d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z"
        stroke={color}
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Circle cx={12} cy={12} r={3} stroke={color} strokeWidth={1.8} />
    </Svg>
  );
}

/** Przekreślone oko - "ukryj hasło". */
export function EyeOffIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Path
        d="M3 3l18 18M10.6 10.6a3 3 0 004.24 4.24M9.4 5.3A10.8 10.8 0 0112 5c6.4 0 10 7 10 7a13.5 13.5 0 01-3.2 3.9M6.2 6.2A13.4 13.4 0 002 12s3.6 7 10 7c1.2 0 2.3-.2 3.3-.6"
        stroke={color}
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Zakrzywiona strzałka cofania - zakładka Zwroty. Ten sam kształt co w
 *  apce desktopowej (spójna ikonografia obu klientów). */
export function UndoIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Path
        d="M3 12a9 9 0 1 0 3-6.7"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path d="M3 4v5h5" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

/** Dymek rozmowy - zakładka Dyskusje. */
export function ChatIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Path
        d="M4 4h16v11H8l-4 4V4Z"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Koperta - zakładka Skrzynka. */
export function MailIcon({ size = defaults.size, color = defaults.color }: IconProps) {
  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <Rect x={3} y={6} width={18} height={13} rx={1.5} stroke={color} strokeWidth={2} />
      <Path d="M3 7l9 6 9-6" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}
