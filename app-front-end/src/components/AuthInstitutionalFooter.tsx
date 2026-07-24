/** Bottom chrome on login / session summary screens. */
export const INSTITUTIONAL_ACCESS_COPY = 'Confidential · Institutional Access';
export const COLOPHON_COPY = 'Set in Playfair Display, Figtree & Space Mono · London · San Francisco';

export const institutionalAccessFooterClass =
  'type-label-section m-0';

export default function AuthInstitutionalFooter() {
  return (
    <div className="flex flex-col items-center gap-phi-2">
      <p className={institutionalAccessFooterClass}>{INSTITUTIONAL_ACCESS_COPY}</p>
      <p className={institutionalAccessFooterClass}>{COLOPHON_COPY}</p>
    </div>
  );
}
