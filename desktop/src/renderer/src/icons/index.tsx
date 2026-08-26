/**
 * Ikony liniowe 1:1 z koncepcja wizualna (viewBox 24x24, stroke 1.6,
 * round caps). Kolor przez `currentColor`, sterowany klasami text-*.
 *
 * Sciezki ikon nawigacji, paska narzedzi i palety polecen sa przepisane
 * doslownie z ordly-koncepcja-wizualna.html - nie "podobne", tylko te
 * same. Ikony, ktorych koncepcja nie pokazuje (np. kosz, olowek), sa
 * dorysowane w tej samej konwencji.
 */
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function base({ size = 17, ...props }: IconProps) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none" as const,
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    ...props,
  };
}

// ---------------------------------------------------------------- nawigacja

export function HomeIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4 11.5 12 4l8 7.5" />
      <path d="M6 10v9a1 1 0 0 0 1 1h3v-6h4v6h3a1 1 0 0 0 1-1v-9" />
    </svg>
  );
}

export function BoxIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M3.5 8.5 12 4l8.5 4.5V16L12 20.5 3.5 16Z" />
      <path d="M3.5 8.5 12 13l8.5-4.5" />
      <path d="M12 13v7.5" />
    </svg>
  );
}

export function ChatIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4 5h16v10.5H9L4 19Z" />
    </svg>
  );
}

export function GridIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="4" y="4" width="7" height="7" rx="1.2" />
      <rect x="13" y="4" width="7" height="7" rx="1.2" />
      <rect x="4" y="13" width="7" height="7" rx="1.2" />
      <rect x="13" y="13" width="7" height="7" rx="1.2" />
    </svg>
  );
}

export function MailIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="3.5" y="5.5" width="17" height="13" rx="1.6" />
      <path d="m4 6.5 8 6.5 8-6.5" />
    </svg>
  );
}

export function ReturnIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4 10h11a4.5 4.5 0 0 1 0 9H10" />
      <path d="m8 6-4 4 4 4" />
    </svg>
  );
}

export function TruckIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M3 16V7h9v9" />
      <path d="M12 10h5l3 3v3h-8" />
      <circle cx="7" cy="18" r="1.6" />
      <circle cx="17" cy="18" r="1.6" />
    </svg>
  );
}

export function ChartIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M5 19V10M12 19V5M19 19v-7" />
    </svg>
  );
}

export function CalendarIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="3.5" y="5" width="17" height="15" rx="1.6" />
      <path d="M3.5 9.5h17M8 3v4M16 3v4" />
      <circle cx="8" cy="14" r="1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="14" r="1" fill="currentColor" stroke="none" />
      <circle cx="16" cy="14" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function GearIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 13.5a7.6 7.6 0 0 0 0-3L21 9l-2-3.5-1.9.7a7.6 7.6 0 0 0-2.6-1.5L14 3h-4l-.5 2.2a7.6 7.6 0 0 0-2.6 1.5L5 6l-2 3.5 1.6 1.5a7.6 7.6 0 0 0 0 3L3 15.5 5 19l1.9-.7a7.6 7.6 0 0 0 2.6 1.5L10 22h4l.5-2.2a7.6 7.6 0 0 0 2.6-1.5l1.9.7 2-3.5Z" />
    </svg>
  );
}

// ------------------------------------------------------------------ akcje

export function SearchIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m20 20-3.8-3.8" />
    </svg>
  );
}

export function PrinterIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M6 9V3h12v6" />
      <rect x="5" y="13" width="14" height="7" rx="1" />
    </svg>
  );
}

export function FilterIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 3v18M3 8h18M3 16h18" />
    </svg>
  );
}

export function SortIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4 6h16M7 12h10M10 18h4" />
    </svg>
  );
}

export function ExportIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 4v11m0 0-4-4m4 4 4-4" />
      <path d="M5 19h14" />
    </svg>
  );
}

export function CheckIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="m4 12 5 5L20 6" />
    </svg>
  );
}

export function RefreshIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M20 11A8 8 0 0 0 5.3 7.3M4 13a8 8 0 0 0 14.7 3.7" />
      <path d="M4 4v5h5M20 20v-5h-5" />
    </svg>
  );
}

export function PlusIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function MinusIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M5 12h14" />
    </svg>
  );
}

export function CloseIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

export function TrashIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" />
    </svg>
  );
}

export function PencilIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4 20h4L19.5 8.5a2.1 2.1 0 0 0-3-3L5 17v3Z" />
    </svg>
  );
}

export function ClipIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M20 11.5 12.3 19a4.6 4.6 0 0 1-6.5-6.5l7.7-7.7a3 3 0 0 1 4.3 4.3l-7.7 7.7a1.5 1.5 0 0 1-2.1-2.1l7-7" />
    </svg>
  );
}

export function LinkIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1.7 1.7" />
      <path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1.7-1.7" />
    </svg>
  );
}

export function TemplateIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="4.5" y="3.5" width="15" height="17" rx="2" />
      <path d="M8 8h8M8 12h8M8 16h5" />
    </svg>
  );
}

export function SendIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4.5 11.5 20 5l-6.5 15.5-2.2-6.8-6.8-2.2Z" />
    </svg>
  );
}

export function ExternalIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M14 4h6v6M20 4l-9 9" />
      <path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
    </svg>
  );
}

export function LogoutIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M10 20H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h5" />
      <path d="M15 8l4 4-4 4M19 12H9" />
    </svg>
  );
}

export function AlertIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 4.5 21 19.5H3Z" />
      <path d="M12 10v4M12 17h.01" />
    </svg>
  );
}

export function ServerIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="3.5" y="4.5" width="17" height="6" rx="1.5" />
      <rect x="3.5" y="13.5" width="17" height="6" rx="1.5" />
      <path d="M7 7.5h.01M7 16.5h.01" />
    </svg>
  );
}

export function UserIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="12" cy="8" r="3.6" />
      <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
    </svg>
  );
}

export function LockIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="4.5" y="10.5" width="15" height="9.5" rx="2" />
      <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
    </svg>
  );
}

export function EyeIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

export function EyeOffIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4 4l16 16" />
      <path d="M9.9 5.9A9.6 9.6 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-3.4 4.1M6.4 7.9A17 17 0 0 0 2.5 12S6 18.5 12 18.5c.8 0 1.5-.1 2.2-.3" />
      <path d="M9.9 10.2a3 3 0 0 0 4 4.2" />
    </svg>
  );
}

export function TagIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M11.5 3.5H20v8.5l-8.5 8.5-8.5-8.5Z" />
      <circle cx="16" cy="8" r="1.4" />
    </svg>
  );
}

/** Iskra - generowanie oferty przez AI (Ordlak). */
export function SparkIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 3.5 13.9 9l5.6 2-5.6 2-1.9 5.5L10.1 13 4.5 11l5.6-2Z" />
      <path d="M18.5 4v3M20 5.5h-3" />
    </svg>
  );
}

/** Strzalka rozwijania - obracana przez CSS, wiec rysowana raz, w prawo. */
export function ChevronIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="m9 5 7 7-7 7" />
    </svg>
  );
}

export function ClockIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </svg>
  );
}
