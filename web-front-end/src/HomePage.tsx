import { useEffect, useState } from 'react';
import { useReducedMotion } from 'framer-motion';
import GalleryFrame from './components/GalleryFrame';
import GalleryLoader from './components/GalleryLoader';
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
  const reduce = useReducedMotion();
  const [entered, setEntered] = useState(false);
  const [showLoader, setShowLoader] = useState(false);

  // Arrival overlay: plays once per session, client-only. Resting state (entered
  // = false) must stay fully visible at rest — see HeroPlate/GalleryFrame's
  // `enter` prop — so a static/prerendered render never hides anything; this
  // effect only ever adds the loader + settle animation on top.
  useEffect(() => {
    let seen = true;
    try {
      seen = typeof window === 'undefined' || sessionStorage.getItem('aethria-intro-seen') === '1';
    } catch {
      // ponytail: private-mode Safari — treat as seen, skip the loader
    }
    if (reduce || seen) {
      setEntered(true);
      return;
    }
    setShowLoader(true);
  }, [reduce]);

  // Honour any incoming plate hash — old bookmarked #access links, and the
  // frame nav arriving from another route (e.g. /team → /home#market).
  useEffect(() => {
    const hash = window.location.hash;
    if (!hash) return;
    const el = document.getElementById(hash.slice(1));
    if (!el) return;
    const t = setTimeout(() => el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' }), 300);
    return () => clearTimeout(t);
  }, [reduce]);

  return (
    <div
      className="home-page relative flex min-h-[100dvh] w-full flex-col overflow-x-hidden"
      style={{ backgroundColor: 'var(--surface-base)', color: 'var(--text-primary)' }}
    >
      {showLoader && (
        <GalleryLoader
          onLift={() => setEntered(true)}
          onDone={() => setShowLoader(false)}
        />
      )}
      <GalleryFrame active="home" enter={entered} quiet />
      <HeroPlate enter={entered} />

      <div className="gallery home-gallery">
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
