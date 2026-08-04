/**
 * Nakladka modalna w stylu palety polecen (sekcja 9.1 pkt 11) plus
 * dialog potwierdzenia dla akcji nieodwracalnych.
 *
 * Modal ma pulapke fokusa i zamkniecie Esc (kryterium odbioru 10.3
 * i 9.3 pkt 4) - bez tego czytnik ekranu wychodzil poza dialog, a
 * Tab uciekal do tresci pod spodem.
 */
import * as React from "react";
import { Button } from "./ui";
import { CloseIcon } from "../icons";

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  width?: number;
}

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  width = 540,
}: ModalProps) {
  const boxRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    boxRef.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();

    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = boxRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (!focusable || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    window.addEventListener("keydown", handleKey);
    return () => {
      window.removeEventListener("keydown", handleKey);
      previouslyFocused?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[110] flex items-start justify-center p-4 pt-[10vh]"
      style={{ background: "rgba(4,7,6,.72)", backdropFilter: "blur(7px)" }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        ref={boxRef}
        style={{ width: `min(${width}px, 92vw)` }}
        onClick={(event) => event.stopPropagation()}
        className="animate-cmd-in flex max-h-[80vh] flex-col overflow-hidden rounded-lg border border-line-strong bg-panel shadow-palette"
      >
        <div className="flex items-start gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0 flex-1">
            <h3 className="o-section-title truncate">{title}</h3>
            {subtitle && (
              <p className="o-mono mt-1 truncate text-[11px] text-slate-dim">{subtitle}</p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Zamknij"
            className="shrink-0 text-slate-dim transition-colors hover:text-white"
          >
            <CloseIcon size={16} />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>

        {footer && (
          <div className="flex items-center justify-end gap-2 border-t border-line px-5 py-3.5">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  /** Mowi CO sie stanie - nie "czy na pewno?", tylko konkret. */
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onClose: () => void;
  pending?: boolean;
}

/** Potwierdzenie akcji nieodwracalnej - przycisk potwierdzenia w wariancie koralowym. */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  onConfirm,
  onClose,
  pending = false,
}: ConfirmDialogProps) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      width={420}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={pending}>
            Anuluj
          </Button>
          <Button
            onClick={onConfirm}
            disabled={pending}
            className="!bg-coral !text-[#2A0D05] hover:brightness-110"
          >
            {pending ? "Chwileczkę…" : confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-[12.5px] leading-[1.6] text-slate">{message}</p>
    </Modal>
  );
}
