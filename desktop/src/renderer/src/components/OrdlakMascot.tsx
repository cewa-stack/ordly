/**
 * Ordlak - maskotka asystenta, OSOBNA postac od Ordiego.
 *
 * Podzial ról: Ordi (`Mascot.tsx`) jest wskaznikiem stanu CALEJ aplikacji,
 * Ordlak jest twarza asystenta i reaguje wylacznie na to, co dzieje sie
 * w rozmowie:
 * - "idle"     - czat czeka na pytanie
 * - "thinking" - asystent odpytuje dane
 * - "happy"    - rozmowa trwa, odpowiedz jest na ekranie
 */
import mascotHappy from "../assets/mascot_ordlak_happy.png";
import mascotIdle from "../assets/mascot_ordlak_idle.png";
import mascotThinking from "../assets/mascot_ordlak_thinking.png";

export type OrdlakPose = "idle" | "thinking" | "happy";

const POSE_SRC: Record<OrdlakPose, string> = {
  idle: mascotIdle,
  thinking: mascotThinking,
  happy: mascotHappy,
};

interface OrdlakMascotProps {
  pose?: OrdlakPose;
  size?: number;
  /** Unoszenie w spoczynku. Wylaczone w trakcie generowania. */
  floaty?: boolean;
  className?: string;
}

export function OrdlakMascot({
  pose = "idle",
  size = 88,
  floaty = true,
  className = "",
}: OrdlakMascotProps) {
  return (
    <img
      src={POSE_SRC[pose]}
      alt="Ordlak"
      width={size}
      height={size}
      className={`${floaty && pose !== "thinking" ? "animate-bob-slow" : ""} ${className}`}
      style={{ objectFit: "contain", width: size, height: size }}
    />
  );
}
