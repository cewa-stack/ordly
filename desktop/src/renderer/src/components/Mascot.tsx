/**
 * Ordi - maskotka ORDLY, uzywana jako WSKAZNIK STANU SYSTEMU, nie ozdoba.
 *
 * Cztery pozy, kazda o innym znaczeniu (sekcja 3.1 specyfikacji):
 * - "idle"   - spoczynek, stan domyslny wskaznika
 * - "think"  - praca / uwaga (synchronizacja, niski stan magazynowy)
 * - "happy"  - sukces (zakonczona akcja, pusta lista, ktora jest dobra
 *              wiadomoscia)
 * - "orders" - kontekst zamowien (hero ekranu Start)
 *
 * Zasada jednego Ordiego: na jednym widoku w jednym momencie Ordi
 * wystepuje RAZ w roli wskaznika. Male ikony 22 px przy pozycjach
 * niskiego stanu sa wyjatkiem - to etykiety, nie wskazniki.
 */
import mascotIdle from "../assets/mascot_stats.png";
import mascotHappy from "../assets/mascot_happy.png";
import mascotOrders from "../assets/mascot_orders.png";
import mascotThink from "../assets/mascot_thinking.png";

export type OrdiPose = "idle" | "think" | "happy" | "orders";

const POSE_SRC: Record<OrdiPose, string> = {
  idle: mascotIdle,
  think: mascotThink,
  happy: mascotHappy,
  orders: mascotOrders,
};

interface MascotProps {
  pose?: OrdiPose;
  size?: number;
  /** Unoszenie w spoczynku (3.4 s w petli). Wylaczone w fazie pracy. */
  floaty?: boolean;
  className?: string;
}

export function Mascot({
  pose = "idle",
  size = 88,
  floaty = true,
  className = "",
}: MascotProps) {
  return (
    <img
      src={POSE_SRC[pose]}
      alt="Ordi"
      width={size}
      height={size}
      className={`${floaty ? "animate-bob-slow" : ""} ${className}`}
      style={{ objectFit: "contain", width: size, height: size }}
    />
  );
}
