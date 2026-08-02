/**
 * Ikony liniowe (stroke, nie fill) - styl 1:1 z mobile/src/icons/index.tsx
 * (viewBox 24x24, stroke-width 2, round caps). Kolor przez `currentColor`,
 * sterowany klasami text-* z Tailwind (idiomatyczne dla SVG w web, w
 * odroznieniu od React Native gdzie kolor trzeba podawac jawnie).
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
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    ...props,
  };
}

export function ServerIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="3" y="4" width="18" height="6" rx="1.5" />
      <rect x="3" y="14" width="18" height="6" rx="1.5" />
      <circle cx="7" cy="7" r="1" fill="currentColor" stroke="none" />
      <circle cx="7" cy="17" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function UserIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c0-4 3.6-6 8-6s8 2 8 6" />
    </svg>
  );
}

export function LockIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  );
}

export function EyeIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

export function EyeOffIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M3 3l18 18" />
      <path d="M10.6 5.1A10.6 10.6 0 0 1 12 5c6.4 0 10 7 10 7a17.6 17.6 0 0 1-3.1 3.9M6.5 6.8C4 8.4 2 12 2 12s3.6 7 10 7a9.6 9.6 0 0 0 4.2-.9" />
      <path d="M9.5 9.8a3 3 0 0 0 4.2 4.2" />
    </svg>
  );
}

export function BoxIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M3 8l9-5 9 5-9 5-9-5Z" />
      <path d="M3 8v8l9 5 9-5V8" />
      <path d="M12 13v8" />
    </svg>
  );
}

export function ReceiptIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M6 2h12v19l-3-2-3 2-3-2-3 2V2Z" />
      <path d="M9 8h6M9 12h6" />
    </svg>
  );
}

export function UndoIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M3 12a9 9 0 1 0 3-6.7" />
      <path d="M3 4v5h5" />
    </svg>
  );
}

export function ChatIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4 4h16v11H8l-4 4V4Z" />
    </svg>
  );
}

export function WarehouseIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M3 21V9l9-6 9 6v12" />
      <path d="M9 21v-7h6v7" />
    </svg>
  );
}

export function MailIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="3" y="6" width="18" height="13" rx="1.5" />
      <path d="M3 7l9 6 9-6" />
    </svg>
  );
}

export function TagIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M20.5 8 12 3 3.5 8v8L12 21l8.5-5V8Z" />
      <path d="M3.5 8 12 13l8.5-5M12 13v8" />
    </svg>
  );
}

export function BarsIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="4" y="14" width="4" height="7" rx="1" />
      <rect x="10" y="9" width="4" height="12" rx="1" />
      <rect x="16" y="4" width="4" height="17" rx="1" />
    </svg>
  );
}

export function SearchIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </svg>
  );
}

export function PlusIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 20V4M4 12h16" />
    </svg>
  );
}

export function GearIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9c.2.7.7 1.2 1.5 1.4h.1a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
    </svg>
  );
}

export function LogoutIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="M16 17l5-5-5-5" />
      <path d="M21 12H9" />
    </svg>
  );
}

export function RefreshIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M3 12a9 9 0 0 1 15.4-6.4L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-15.4 6.4L3 16" />
      <path d="M3 21v-5h5" />
    </svg>
  );
}
