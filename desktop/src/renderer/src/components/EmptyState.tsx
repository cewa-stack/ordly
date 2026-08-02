import { Mascot, type MascotPose } from "./Mascot";

interface EmptyStateProps {
  pose: MascotPose;
  title: string;
  description?: string;
}

/** Pusty stan ekranu - maskotka (poza niesie znaczenie, patrz Mascot.tsx) + tytuł + opis. */
export function EmptyState({ pose, title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-2 py-16 text-center">
      <Mascot pose={pose} size={72} floaty={false} className="mb-1" />
      <p className="text-callout-semibold">{title}</p>
      {description && <p className="max-w-[320px] text-footnote text-text-secondary">{description}</p>}
    </div>
  );
}
