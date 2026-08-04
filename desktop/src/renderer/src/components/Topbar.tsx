/**
 * Gorny pasek obszaru roboczego (sekcja 4.1/4.4): tytul ekranu +
 * okruszek, pole szukania otwierajace palete polecen, awatar.
 *
 * Tytul i okruszek zmieniaja sie RAZEM z ekranem - okruszek niesie stan
 * (np. aktywny filtr), zeby uzytkownik widzial, na co patrzy.
 */
import { SearchIcon } from "../icons";

interface TopbarProps {
  title: string;
  crumb: string;
  initials: string;
  onOpenPalette: () => void;
}

export function Topbar({ title, crumb, initials, onOpenPalette }: TopbarProps) {
  return (
    <div className="flex shrink-0 items-center gap-3.5 border-b border-line px-6 py-[15px]">
      <div className="min-w-0">
        <h2 className="o-screen-title truncate">{title}</h2>
        <div className="o-mono truncate pl-0.5 text-[10.5px] text-slate-dim">{crumb}</div>
      </div>

      <button
        onClick={onOpenPalette}
        className="ml-auto flex w-[236px] items-center gap-[9px] rounded-[9px] border border-line bg-panel-2 px-[11px] py-2 text-[12.5px] text-slate-dim transition-[border-color,color] duration-[180ms] ease-ordly hover:border-line-strong hover:text-slate"
      >
        <SearchIcon size={14} className="opacity-75" />
        Szukaj lub przejdź do…
        <span className="o-mono ml-auto rounded-[5px] border border-line-strong bg-ink-raised px-1.5 py-0.5 text-[10px] text-slate-dim">
          Ctrl K
        </span>
      </button>

      <div
        className="o-display flex h-[31px] w-[31px] shrink-0 items-center justify-center rounded-full border border-line-strong text-[11px] font-semibold text-slate"
        style={{ background: "linear-gradient(150deg, #3D544D, #1A2622)" }}
      >
        {initials}
      </div>
    </div>
  );
}
