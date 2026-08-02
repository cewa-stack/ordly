/**
 * Maskotka ORDLY - uzywana WYLACZNIE w: logowanie, puste stany, sukces,
 * blad. Nigdy w sidebarze/dashboardzie/ustawieniach jako powtarzalny
 * element chrome (ta sama zasada co mobile/src/components/Mascot.tsx).
 *
 * Kazda poza niesie inne znaczenie, zeby te same puste stany nie byly
 * wizualnie monotonne w calej appce:
 * - "default" (clipboard) - logowanie, ogolny stan "do zrobienia".
 * - "orders"  - pusta lista zamowien (czeka na pierwsze/kolejne).
 * - "happy"   - pusty stan, ktory jest DOBRA wiadomoscia (zero zwrotow,
 *               zero otwartych dyskusji).
 * - "thinking"- szukanie/filtrowanie nic nie znalazlo.
 * - "stats"   - brak danych do statystyk/prognozy.
 *
 * Wszystkie pliki maja teraz prawdziwa przezroczystosc (usunieto tlo) -
 * renderowane bezposrednio, bez dodatkowej "plytki" w tle.
 */
import mascotDefault from "../assets/mascot.png";
import mascotHappy from "../assets/mascot_happy.png";
import mascotOrders from "../assets/mascot_orders.png";
import mascotStats from "../assets/mascot_stats.png";
import mascotThinking from "../assets/mascot_thinking.png";

export type MascotPose = "default" | "happy" | "orders" | "thinking" | "stats";

const POSE_SRC: Record<MascotPose, string> = {
  default: mascotDefault,
  happy: mascotHappy,
  orders: mascotOrders,
  thinking: mascotThinking,
  stats: mascotStats,
};

interface MascotProps {
  pose?: MascotPose;
  size?: number;
  floaty?: boolean;
  className?: string;
}

export function Mascot({ pose = "default", size = 96, floaty = true, className = "" }: MascotProps) {
  return (
    <img
      src={POSE_SRC[pose]}
      alt="Maskotka ORDLY"
      width={size}
      height={size}
      className={`${floaty ? "animate-floaty" : ""} ${className}`}
      style={{ objectFit: "contain" }}
    />
  );
}
