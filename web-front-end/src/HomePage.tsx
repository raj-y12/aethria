import { useEffect } from 'react';
import GalleryFrame from './components/GalleryFrame';
import HeroPlate from './components/HeroPlate';
import Plate from './components/Plate';

export default function HomePage() {
  // The application form lives further down the gallery spine (Task 11); honour
  // old bookmarked/shared #access links.
  useEffect(() => {
    if (window.location.hash !== '#access') return;
    const el = document.getElementById('access');
    if (!el) return;
    const t = setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 300);
    return () => clearTimeout(t);
  }, []);

  return (
    <div
      className="relative flex min-h-[100dvh] w-full flex-col overflow-x-hidden"
      style={{ backgroundColor: 'var(--surface-base)', color: 'var(--text-primary)' }}
    >
      <GalleryFrame />
      <HeroPlate />

      <div className="gallery">
        {/* Placeholder — Phase 2 (Tasks 8–11) replaces this with the real plate spine
            (Market, Record, Review, Lookup, Access, Colophon). */}
        <Plate
          id="market"
          index="01 — 08"
          title="The Market"
          capLeft="The Market — Plate 01"
          capRight="Placeholder — plates land in Phase 2"
        >
          <div style={{ minHeight: '200px' }} />
        </Plate>
      </div>
    </div>
  );
}
