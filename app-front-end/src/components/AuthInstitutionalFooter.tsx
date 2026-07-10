/** Bottom chrome on login / session summary screens. */
export const INSTITUTIONAL_ACCESS_COPY = 'Confidential · Institutional Access';

export const institutionalAccessFooterClass =
  'type-meta uppercase tracking-[0.22em] text-oxford/60 m-0';

export default function AuthInstitutionalFooter() {
  return <p className={institutionalAccessFooterClass}>{INSTITUTIONAL_ACCESS_COPY}</p>;
}
