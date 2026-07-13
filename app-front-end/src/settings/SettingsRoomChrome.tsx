import type { KeyboardEvent } from 'react';
import type { Settings } from '../api/settings';
import RoomHeader from '../components/RoomHeader';
import OperationsStrip from './OperationsStrip';
import type { PendingChange, SettingsTab } from './settingsModel';

interface SettingsRoomChromeProps {
  activeTab: SettingsTab;
  settings: Settings;
  storageUnavailable: boolean;
  pendingChanges: PendingChange[];
  saving: boolean;
  thesisVersion: string;
  policyVersion: string;
  onSettingsChange: (settings: Settings) => void;
  onTabChange: (tab: SettingsTab) => void;
  onTabKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void;
  onDeploy: () => void;
  onReset: () => void;
}

function ChromeReadout({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-phi-1">
      <span className="type-data text-oxford">{value}</span>
      <span className="type-label-section">{label}</span>
    </div>
  );
}

export default function SettingsRoomChrome({
  activeTab,
  settings,
  storageUnavailable,
  pendingChanges,
  saving,
  thesisVersion,
  policyVersion,
  onSettingsChange,
  onTabChange,
  onTabKeyDown,
  onDeploy,
  onReset,
}: SettingsRoomChromeProps) {
  const unsaved = pendingChanges.length > 0;

  return (
    <>
      <RoomHeader
        className="pb-phi-5"
        eyebrow="The operating model"
        title="Settings"
        sub={(
          <p className="max-w-[62ch] type-body-sm leading-relaxed text-oxford/60">
            Configuration below remains draft until deployed. Pipeline controls save immediately.
          </p>
        )}
        readouts={(
          <div className="flex flex-wrap items-end justify-end gap-x-phi-6 gap-y-phi-4">
            <ChromeReadout label="Deployment" value={unsaved ? 'Draft' : 'Live'} />
            <ChromeReadout
              label="Changes"
              value={unsaved ? `${pendingChanges.length} pending` : 'No pending changes'}
            />
            <ChromeReadout label="Thesis" value={thesisVersion} />
            <ChromeReadout label="Policy" value={policyVersion} />
            <div className="flex items-center gap-phi-3">
              <button
                type="button"
                onClick={onReset}
                disabled={saving}
                className="type-action inline-flex min-h-11 items-center justify-center px-phi-2 transition-colors hover:text-oxford disabled:cursor-not-allowed disabled:opacity-40 btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
              >
                Reset
              </button>
              <button
                type="button"
                onClick={onDeploy}
                disabled={saving || !unsaved}
                className="btn-aethria-solid disabled:cursor-not-allowed disabled:opacity-40"
              >
                {saving ? 'Deploying…' : 'Deploy changes'}
              </button>
            </div>
          </div>
        )}
      />

      <OperationsStrip
        settings={settings}
        storageUnavailable={storageUnavailable}
        onSettingsChange={onSettingsChange}
      />

      <nav
        role="tablist"
        aria-label="Settings mode"
        className="flex items-center gap-phi-5 overflow-x-auto no-scrollbar pt-phi-3"
      >
        {(['decision', 'admin'] as const).map((tab) => {
          const selected = activeTab === tab;
          const label = tab === 'decision' ? 'Decision' : 'Administration';
          return (
            <button
              key={tab}
              id={`settings-tab-${tab}`}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={`settings-panel-${tab}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => onTabChange(tab)}
              onKeyDown={onTabKeyDown}
              className={`relative -mb-px shrink-0 border-b pb-phi-3 pt-phi-1 type-label-tab transition-colors btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 ${
                selected
                  ? 'border-oxford font-semibold text-oxford'
                  : 'border-transparent font-normal text-oxford/60 hover:text-oxford/70'
              }`}
            >
              {label}
            </button>
          );
        })}
      </nav>
    </>
  );
}
