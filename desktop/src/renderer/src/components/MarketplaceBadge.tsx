/**
 * Odznaka marketplace - obecnie tylko Allegro ma prawdziwą integrację
 * (Amazon/eBay to puste foldery-szkielety w backendzie, nigdy nie
 * działały równolegle) - żadna inna wartość nie dostaje odznaki z
 * kolorem marki, żeby nie sugerować wsparcia, którego nie ma.
 */
const MARKETPLACE_STYLE: Record<string, { label: string; color: string }> = {
  allegro: { label: "Allegro", color: "#FF5A00" },
};

interface MarketplaceBadgeProps {
  marketplace: string;
}

export function MarketplaceBadge({ marketplace }: MarketplaceBadgeProps) {
  const style = MARKETPLACE_STYLE[marketplace.toLowerCase()];
  if (!style) {
    return <span className="font-mono text-[11px] text-text-dim">{marketplace}</span>;
  }
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full py-0.5 pl-0.5 pr-2.5 text-[11px] font-bold"
      style={{ backgroundColor: `${style.color}26`, color: style.color }}
    >
      <span
        className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px] text-white"
        style={{ backgroundColor: style.color }}
      >
        {style.label.charAt(0)}
      </span>
      {style.label}
    </span>
  );
}
