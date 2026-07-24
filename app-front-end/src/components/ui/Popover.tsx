import { useId, useRef, useState, type ReactNode } from 'react';

interface PopoverProps {
  /** The hover/focus target (usually a row or an info glyph). */
  children: ReactNode;
  /** Floating content shown on hover/focus. */
  content: ReactNode;
  /** Accessible label for the trigger when its visible content is non-textual. */
  label?: string;
  /** Horizontal anchoring of the panel relative to the trigger. */
  align?: 'start' | 'end';
  className?: string;
  triggerClassName?: string;
  panelClassName?: string;
  reduceMotion?: boolean;
}

/**
 * Lightweight, dependency-free popover for progressive disclosure.
 *
 * Opens on hover OR keyboard focus, closes on blur / mouse-leave / Escape. The panel
 * stays open while the pointer is over either the trigger or the panel (single hover
 * region), so users can't "fall off" reaching for it. Content is informational, so the
 * panel is `role="tooltip"` and linked via `aria-describedby`.
 */
export default function Popover({
  children,
  content,
  label,
  align = 'start',
  className = '',
  triggerClassName = '',
  panelClassName = '',
  reduceMotion = false,
}: PopoverProps) {
  const [open, setOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const panelId = useId();

  const show = () => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    setOpen(true);
  };
  // Small grace period so moving the pointer from trigger to panel doesn't dismiss it.
  const scheduleHide = () => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setOpen(false), 80);
  };

  return (
    <span
      className={`relative inline-flex ${className}`}
      onMouseEnter={show}
      onMouseLeave={scheduleHide}
      onFocus={show}
      onBlur={scheduleHide}
      onKeyDown={(e) => {
        if (e.key === 'Escape') setOpen(false);
      }}
    >
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-describedby={open ? panelId : undefined}
        className={triggerClassName}
        onClick={() => setOpen((v) => !v)}
      >
        {children}
      </button>
      <span
        id={panelId}
        role="tooltip"
        hidden={!open}
        className={[
          'absolute top-full z-30 mt-2 w-[min(22rem,78vw)] cursor-default',
          'border border-oxford/15 bg-paper px-3.5 py-3 text-left shadow-[0_10px_30px_-12px_rgba(10,22,41,0.35)]',
          align === 'end' ? 'right-0' : 'left-0',
          reduceMotion ? '' : 'transition-opacity duration-150',
          open ? 'opacity-100' : 'opacity-0',
          panelClassName,
        ].join(' ')}
      >
        {content}
      </span>
    </span>
  );
}
