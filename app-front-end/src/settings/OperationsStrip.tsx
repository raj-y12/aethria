import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { patchSettings, type Settings } from '../api/settings';

type OperationKey = 'scouts' | 'reviewers' | 'partners' | 'budget';

interface OperationsStripProps {
  settings: Settings;
  storageUnavailable: boolean;
  onSettingsChange: (settings: Settings) => void;
  /** 'bar' = horizontal (mobile top); 'rail' = vertical (desktop rail foot). */
  variant?: 'bar' | 'rail';
}

const controls: Array<{
  key: OperationKey;
  label: string;
}> = [
  { key: 'scouts', label: 'Scouts' },
  { key: 'reviewers', label: 'Reviewers' },
  { key: 'partners', label: 'Partners' },
  { key: 'budget', label: 'Cost budget' },
];

function isEnabled(settings: Settings, key: OperationKey): boolean {
  if (key === 'budget') return settings.cost_budget.enabled;
  if (key === 'scouts') return settings.agent_config.scouts_enabled;
  if (key === 'reviewers') return settings.agent_config.reviewers_enabled;
  return settings.agent_config.partners_enabled;
}

function updateOperation(settings: Settings, key: OperationKey, enabled: boolean): Settings {
  if (key === 'budget') {
    return { ...settings, cost_budget: { ...settings.cost_budget, enabled } };
  }
  const property = key === 'scouts'
    ? 'scouts_enabled'
    : key === 'reviewers'
      ? 'reviewers_enabled'
      : 'partners_enabled';
  return {
    ...settings,
    agent_config: { ...settings.agent_config, [property]: enabled },
  };
}

function preservePendingValues(
  authoritative: Settings,
  optimistic: Settings,
  pending: Set<OperationKey>,
): Settings {
  let merged = authoritative;
  for (const key of pending) {
    merged = updateOperation(merged, key, isEnabled(optimistic, key));
  }
  return merged;
}

export default function OperationsStrip({
  settings,
  storageUnavailable,
  onSettingsChange,
  variant = 'bar',
}: OperationsStripProps) {
  const isRail = variant === 'rail';
  const queryClient = useQueryClient();
  const [optimistic, setOptimistic] = useState(settings);
  const optimisticRef = useRef(settings);
  const pendingRef = useRef(new Set<OperationKey>());
  const [pending, setPending] = useState<Set<OperationKey>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const commitOptimistic = (next: Settings) => {
    optimisticRef.current = next;
    setOptimistic(next);
  };

  useEffect(() => {
    const next = preservePendingValues(settings, optimisticRef.current, pendingRef.current);
    optimisticRef.current = next;
    setOptimistic(next);
  }, [settings]);

  const setOperationPending = (key: OperationKey, value: boolean) => {
    const next = new Set(pendingRef.current);
    if (value) next.add(key);
    else next.delete(key);
    pendingRef.current = next;
    setPending(next);
  };

  const save = async (key: OperationKey, enabled: boolean) => {
    const previousEnabled = isEnabled(optimisticRef.current, key);
    const next = updateOperation(optimisticRef.current, key, enabled);
    commitOptimistic(next);
    setOperationPending(key, true);
    setError(null);

    const body = key === 'budget'
      ? { cost_budget: next.cost_budget }
      : { agent_config: next.agent_config };
    const result = await patchSettings(body);
    setOperationPending(key, false);

    if (result.error || !result.data) {
      commitOptimistic(updateOperation(optimisticRef.current, key, previousEnabled));
      setError(
        result.error?.errors[0]
        ?? result.error?.message
        ?? 'We could not save this control. Try again.',
      );
      return;
    }

    const reconciled = preservePendingValues(
      result.data,
      optimisticRef.current,
      pendingRef.current,
    );
    commitOptimistic(reconciled);
    onSettingsChange(reconciled);
    queryClient.setQueryData(['settings'], reconciled);
  };

  return (
    <section
      className={isRail
        ? 'bg-paper px-phi-4 py-phi-5'
        : 'border-b border-oxford/[0.08] bg-paper px-phi-4 py-phi-3 lg:px-phi-6'}
      aria-labelledby="operations-strip-title"
    >
      <div className={isRail ? 'flex flex-col gap-phi-4' : 'flex flex-col gap-phi-3 lg:flex-row lg:items-center lg:gap-phi-6'}>
        <div className={isRail ? '' : 'shrink-0 lg:mr-auto'}>
          <p id="operations-strip-title" className="type-label-section text-xs text-oxford">
            Pipeline controls
          </p>
          <p className="mt-phi-1 type-note text-oxford/70">These controls save immediately.</p>
        </div>

        <div className={isRail ? 'flex flex-col gap-phi-1' : 'grid grid-cols-2 gap-x-phi-5 gap-y-phi-2 sm:grid-cols-4'}>
          {controls.map((control) => {
            const checked = isEnabled(optimistic, control.key);
            const isPending = pending.has(control.key);
            return (
              <div
                key={control.key}
                className="flex min-w-[7.5rem] items-center justify-between gap-phi-2"
              >
                <div>
                  <p className="type-body-sm text-oxford">{control.label}</p>
                  {isPending ? (
                    <p
                      className="mt-0.5 type-status text-xs leading-none text-oxford/70"
                      data-operation-status={control.key}
                    >
                      Saving
                    </p>
                  ) : null}
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-label={control.label}
                  aria-checked={checked}
                  aria-busy={isPending}
                  disabled={storageUnavailable || isPending}
                  onClick={() => void save(control.key, !checked)}
                  className="group inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center text-oxford transition-opacity disabled:cursor-not-allowed disabled:opacity-45 focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35"
                >
                  <span
                    className={`relative block h-6 w-11 rounded-full transition-colors ${
                      checked ? 'bg-oxford' : 'bg-oxford/[0.09]'
                    }`}
                    aria-hidden
                  >
                    <span
                      className={`absolute top-[3px] block h-4 w-4 rounded-full shadow-sm transition-transform ${
                        checked ? 'translate-x-[22px] bg-paper' : 'translate-x-[3px] bg-oxford/35'
                      }`}
                    />
                  </span>
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {storageUnavailable && (
        <p className="mt-phi-2 type-note text-escalation/80" role="status">
          Storage unavailable. Runtime controls cannot be changed.
        </p>
      )}
      {error && (
        <p className="mt-phi-2 type-note text-escalation/80" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
