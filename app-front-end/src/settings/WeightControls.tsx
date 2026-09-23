import { useEffect, useState } from 'react';

const DEFAULT_INPUT_CLASS =
  // type-data bakes in font-size: 13px, so the display size needs to force past it
  'type-data w-full border-0 bg-transparent p-0 text-center !text-[clamp(1.8rem,3vw,2.6rem)] leading-none text-oxford outline-none focus:ring-0';

/**
 * Commits on blur/Enter, not per keystroke. Rebalancing is destructive — typing
 * "100" one character at a time would redistribute three times and flatten the
 * other weights to an even split with no way back.
 */
export function WeightInput({
  label,
  value,
  onCommit,
  className = DEFAULT_INPUT_CLASS,
}: {
  label: string;
  value: number;
  onCommit: (value: number) => void;
  className?: string;
}) {
  const [text, setText] = useState(String(value));

  useEffect(() => {
    setText(String(value));
  }, [value]);

  const commit = () => {
    const parsed = Number.parseInt(text, 10);
    const next = Number.isFinite(parsed) ? Math.min(100, Math.max(0, parsed)) : value;
    setText(String(next));
    if (next !== value) onCommit(next);
  };

  return (
    <input
      type="number"
      min={0}
      max={100}
      value={text}
      onChange={(event) => setText(event.target.value.replace(/[^\d]/g, ''))}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === 'Enter') event.currentTarget.blur();
      }}
      className={className}
      aria-label={`${label} weight`}
    />
  );
}

/** Replaces the native number spinner, which is unstylable past `appearance: none`. */
export function StepButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="type-data flex h-6 w-6 items-center justify-center leading-none text-oxford/65 transition-colors hover:text-oxford focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 disabled:pointer-events-none disabled:text-oxford/15"
    >
      {children}
    </button>
  );
}
