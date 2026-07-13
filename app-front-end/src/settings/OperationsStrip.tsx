import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { patchSettings, type Settings } from '../api/settings';

type OperationKey = 'scouts' | 'reviewers' | 'partners' | 'budget';

interface OperationsStripProps {
  settings: Settings;
  storageUnavailable: boolean;
  onSettingsChange: (settings: Settings) => void;
}

const controls: Array<{
  key: OperationKey;
  label: string;
  description: string;
}> = [
  { key: 'scouts', label: 'Scouts', description: 'Discover companies' },
  { key: 'reviewers', label: 'Reviewers', description: 'Score opportunities' },
  { key: 'partners', label: 'Partners', description: 'Issue decisions' },
  { key: 'budget', label: 'Cost budget', description: 'Enforce spend limits' },
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
}: OperationsStripProps) {
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
      className="border-y border-oxford/[0.09] bg-paper/95 px-phi-4 py-phi-3 backdrop-blur-sm lg:px-phi-6"
      aria-labelledby="operations-strip-title"
    >
      <div className="flex flex-col gap-phi-3 xl:flex-row xl:items-center xl:gap-phi-6">
        <div className="min-w-[11rem] shrink-0">
          <p id="operations-strip-title" className="type-label-section text-oxford">
            Pipeline controls
          </p>
          <p className="mt-phi-1 type-note text-oxford/60">Changes apply immediately.</p>
        </div>

        <div className="grid min-w-0 flex-1 grid-cols-2 border-l border-t border-oxford/[0.07] md:grid-cols-4 md:border-t-0">
          {controls.map((control) => {
            const checked = isEnabled(optimistic, control.key);
            const isPending = pending.has(control.key);
            return (
              <div
                key={control.key}
                className="flex min-w-0 items-center justify-between gap-phi-2 border-b border-r border-oxford/[0.07] px-phi-3 py-phi-2 md:border-b-0"
              >
                <div className="min-w-0">
                  <p className="type-body-sm text-oxford">{control.label}</p>
                  <p className="mt-0.5 truncate type-note text-oxford/55">{control.description}</p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-label={control.label}
                  aria-checked={checked}
                  aria-busy={isPending}
                  disabled={storageUnavailable || isPending}
                  onClick={() => void save(control.key, !checked)}
                  className="group inline-flex min-h-11 min-w-11 shrink-0 flex-col items-center justify-center gap-1 text-oxford transition-opacity disabled:cursor-not-allowed disabled:opacity-45 focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35"
                >
                  <span
                    className={`relative block h-4 w-8 border transition-colors ${
                      checked ? 'border-oxford bg-oxford' : 'border-oxford/20 bg-oxford/[0.06]'
                    }`}
                    aria-hidden
                  >
                    <span
                      className={`absolute top-0.5 block h-2.5 w-2.5 transition-transform ${
                        checked ? 'translate-x-[17px] bg-paper' : 'translate-x-0.5 bg-oxford/45'
                      }`}
                    />
                  </span>
                  <span className="type-status text-[9px] leading-none text-oxford/60">
                    {isPending ? 'Saving' : checked ? 'On' : 'Off'}
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
