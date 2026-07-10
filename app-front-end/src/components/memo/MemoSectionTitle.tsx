import type { ReactNode } from 'react';

interface MemoSectionTitleProps {
  number: string;
  id: string;
  children: ReactNode;
}

export default function MemoSectionTitle({ number, id, children }: MemoSectionTitleProps) {
  return (
    <div className="memoDocSectionTitle">
      <span className="memoSectionNumber" aria-hidden="true">{number}</span>
      <h2 className="memoDocSectionHead" id={id}>{children}</h2>
    </div>
  );
}
