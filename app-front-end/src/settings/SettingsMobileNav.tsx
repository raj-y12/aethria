import { SETTINGS_GROUPS, SETTINGS_SECTIONS, type SectionId } from './settingsModel';

export default function SettingsMobileNav({
  activeSection,
  attentionSection,
  onSelect,
}: {
  activeSection: SectionId;
  attentionSection: SectionId | null;
  onSelect: (id: SectionId) => void;
}) {
  return (
    <nav
      className="sticky top-0 z-20 border-b border-oxford/[0.08] bg-paper px-phi-5 py-phi-2 lg:hidden"
      aria-label="Settings navigation"
    >
      <label htmlFor="settings-mobile-section" className="sr-only">Settings section</label>
      <select
        id="settings-mobile-section"
        value={activeSection}
        onChange={(event) => onSelect(event.target.value as SectionId)}
        className="min-h-11 w-full cursor-pointer border border-oxford/[0.12] bg-paper px-phi-3 type-body-sm text-oxford focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
      >
        {SETTINGS_GROUPS.map((group) => (
          <optgroup
            key={group.id}
            label={`${group.label} — ${group.persistence.toLowerCase()}`}
          >
            {SETTINGS_SECTIONS.filter((section) => section.group === group.id).map((section) => (
              <option key={section.id} value={section.id}>
                {section.short}{attentionSection === section.id ? ' — Needs attention' : ''}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </nav>
  );
}
