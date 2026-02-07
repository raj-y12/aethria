import { useEffect, useState } from 'react';

const OXFORD = '#002147';

export default function CustomCursor() {
  const [pos, setPos] = useState({ x: -100, y: -100 });
  const [expanded, setExpanded] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const hasFinePointer = window.matchMedia('(pointer: fine)').matches;
    if (!hasFinePointer) return;

    setVisible(true);

    const handleMove = (e: MouseEvent) => {
      setPos({ x: e.clientX, y: e.clientY });
      const el = document.elementFromPoint(e.clientX, e.clientY) as HTMLElement | null;
      setExpanded(!!el?.closest('a') || !!el?.closest('[data-cursor-expand]'));
    };

    document.body.style.cursor = 'none';
    window.addEventListener('mousemove', handleMove);

    return () => {
      document.body.style.cursor = '';
      window.removeEventListener('mousemove', handleMove);
    };
  }, []);

  if (!visible) return null;

  return (
    <div
      className="fixed pointer-events-none z-[10000] rounded-full transition-transform duration-300 ease-out"
      style={{
        left: pos.x,
        top: pos.y,
        width: expanded ? 24 : 8,
        height: expanded ? 24 : 8,
        marginLeft: expanded ? -12 : -4,
        marginTop: expanded ? -12 : -4,
        backgroundColor: OXFORD,
        mixBlendMode: 'difference',
      }}
      aria-hidden
    />
  );
}
