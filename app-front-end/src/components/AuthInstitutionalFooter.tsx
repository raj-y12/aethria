/** Bottom chrome on login / session summary screens. */
export const INSTITUTIONAL_ACCESS_COPY = 'Confidential · Institutional Access';

export const institutionalAccessFooterClass =
  'type-label-section m-0';

export default function AuthInstitutionalFooter() {
  return (
    <p className={institutionalAccessFooterClass}>{INSTITUTIONAL_ACCESS_COPY}</p>
  );
}
