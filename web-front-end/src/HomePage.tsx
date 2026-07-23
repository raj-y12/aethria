import { useEffect } from 'react';
import GalleryFrame from './components/GalleryFrame';
import HeroPlate from './components/HeroPlate';
import MarketPlate from './components/plates/MarketPlate';
import RecordPlate from './components/plates/RecordPlate';
import ReviewPlate from './components/plates/ReviewPlate';
import NewsroomPlate from './components/plates/NewsroomPlate';
import CorrectionsPlate from './components/plates/CorrectionsPlate';
import QueryPlate from './components/plates/QueryPlate';
import HoldingsPlate from './components/plates/HoldingsPlate';
import AccessPlate from './components/plates/AccessPlate';

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
        <MarketPlate />
        <RecordPlate />
        <ReviewPlate />
        <NewsroomPlate />
        <CorrectionsPlate />
        <QueryPlate />
        <HoldingsPlate />
        <AccessPlate />
      </div>
    </div>
  );
}
