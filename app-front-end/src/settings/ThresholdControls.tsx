import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { patchSettings, type Settings } from '../api/settings';

type ThresholdKey = 'confidence_threshold' | 'decision_threshold';

interface ThresholdControlsProps {
  settings: Settings;
  storageUnavailable: boolean;
  onSettingsChange: (settings: Settings) => void;
}

const controls: Array<{
  key: ThresholdKey;
  label: string;
  helper: string;
  defaultPercent: number;
}> = [
  {
    key: 'confidence_threshold',
    label: 'Review threshold',
    // Scout's confidence is no longer self-reported (2026-08-19): it's
    // matched-thesis-categories / 3 (sector, stage, geography), so this
    // only ever lands on 0%, 33%, 67%, or 100%. 50% means "at least 2 of 3".
    helper: 'Scout candidates matching fewer mandate categories than this are not reviewed automatically.',
    defaultPercent: 50,
  },
  {
    key: 'decision_threshold',
    label: 'Decision threshold',
    helper: 'Reviewed candidates scoring below this are not decided automatically.',
    defaultPercent: 55,
  },
];

function toPercent(value: number | string | undefined, fallback: number): number {
  const n = typeof value === 'string' ? Number(value) : value;
  if (typeof n !== 'number' || Number.isNaN(n)) return fallback;
  return Math.round(n * 100);
}

export default function ThresholdControls({
  settings,
  storageUnavailable,
  onSettingsChange,
}: ThresholdControlsProps) {
  const queryClient = useQueryClient();
  const [drafts, setDrafts] = useState<Record<ThresholdKey, string>>(() => ({
    confidence_threshold: String(toPercent(settings.agent_config.confidence_threshold, 50)),
    decision_threshold: String(toPercent(settings.agent_config.decision_threshold, 55)),
  }));
  const [pending, setPending] = useState<ThresholdKey | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDrafts({
      confidence_threshold: String(toPercent(settings.agent_config.confidence_threshold, 50)),
      decision_threshold: String(toPercent(settings.agent_config.decision_threshold, 55)),
    });
  }, [settings.agent_config.confidence_threshold, settings.agent_config.decision_threshold]);

  const save = async (key: ThresholdKey, percent: number) => {
    const fraction = Math.max(0, Math.min(100, percent)) / 100;
    const next: Settings = {
      ...settings,
      agent_config: { ...settings.agent_config, [key]: fraction },
    };
    setPending(key);
    setError(null);
    try {
      const result = await patchSettings({ agent_config: next.agent_config });
      if (result.error || !result.data) {
        setDrafts((prev) => ({
          ...prev,
          [key]: String(toPercent(settings.agent_config[key], key === 'confidence_threshold' ? 50 : 55)),
        }));
        setError(
          result.error?.errors[0]
          ?? result.error?.message
          ?? 'We could not save this threshold. Try again.',
        );
        return;
      }
      onSettingsChange(result.data);
      queryClient.setQueryData(['settings'], result.data);
    } catch (requestError) {
      setDrafts((prev) => ({
        ...prev,
        [key]: String(toPercent(settings.agent_config[key], key === 'confidence_threshold' ? 50 : 55)),
      }));
      setError(
        requestError instanceof Error && requestError.message
          ? requestError.message
          : 'We could not save this threshold. Try again.',
      );
    } finally {
      setPending(null);
    }
  };

  return (
    <section
      className="border-b border-oxford/[0.16] bg-paper px-phi-5 py-phi-4 lg:px-phi-6"
      aria-labelledby="threshold-controls-title"
    >
      <p id="threshold-controls-title" className="type-label-section text-xs text-oxford">
        Triage funnel
      </p>
      <p className="mt-phi-1 type-note text-oxford/70">These controls save on blur.</p>
      <div className="mt-phi-3 grid grid-cols-1 gap-x-phi-5 gap-y-phi-3 sm:grid-cols-2">
        {controls.map((control) => {
          const isPending = pending === control.key;
          return (
            <div key={control.key} className="flex flex-col gap-phi-1">
              <label htmlFor={`threshold-${control.key}`} className="type-body-sm text-oxford">
                {control.label}
              </label>
              <div className="flex items-center gap-phi-2">
                <input
                  id={`threshold-${control.key}`}
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  inputMode="numeric"
                  disabled={storageUnavailable || isPending}
                  value={drafts[control.key]}
                  onChange={(e) => setDrafts((prev) => ({ ...prev, [control.key]: e.target.value }))}
                  onBlur={() => {
                    const percent = Number(drafts[control.key]);
                    if (Number.isNaN(percent)) return;
                    void save(control.key, percent);
                  }}
                  aria-busy={isPending}
                  className="w-20 border border-solid border-oxford/15 bg-transparent px-phi-2 py-1.5 type-data text-oxford focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 disabled:cursor-not-allowed disabled:opacity-45"
                />
                <span className="type-body-sm text-oxford/65">%</span>
                {isPending ? <span className="type-status text-xs text-oxford/70">Saving</span> : null}
              </div>
              <p className="type-note text-oxford/60">{control.helper}</p>
            </div>
          );
        })}
      </div>
      {error && (
        <p className="mt-phi-2 type-note text-escalation/80" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
