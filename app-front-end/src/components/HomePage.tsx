import { motion } from 'framer-motion';
import NoiseOverlay from './NoiseOverlay';

interface HomePageProps {
  onEnter: () => void;
}

export default function HomePage({ onEnter }: HomePageProps) {
  return (
    <div className="min-h-screen bg-ivory relative flex items-center justify-center overflow-hidden">
      <NoiseOverlay />
      
      <div className="relative z-10 w-full max-w-6xl px-4 xs:px-6 sm:px-8 lg:px-10 pb-20 sm:pb-24">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="text-center"
        >
          {/* Main Title */}
          <motion.h1
            className="font-display font-bold text-oxford tracking-[-0.05em] mb-8"
            style={{
              fontSize: 'clamp(2rem, 8vw, 4rem)',
              lineHeight: 1.1,
            }}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.1, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          >
            <span className="relative inline-block mr-0.5">
              A
              <motion.span 
                className="absolute bottom-0 left-0 right-0 h-[0.12em] bg-oxford"
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ delay: 0.3, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              />
            </span>
            ethria
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            className="font-body text-graphite/70 text-sm lg:text-base leading-relaxed max-w-2xl mx-auto mb-10 sm:mb-12 px-2"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            Intelligent investment discovery and evaluation system
          </motion.p>

          {/* Enter Button */}
          <motion.button
            onClick={onEnter}
            className="font-sans text-[11px] uppercase tracking-[0.12em] text-charcoal/60 hover:bg-oxford hover:text-ivory hover:border-oxford border border-charcoal/[0.2] px-5 py-2.5 transition-colors duration-300 mb-20"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            Enter System
          </motion.button>
        </motion.div>

        {/* Footer Info */}
        <motion.div
          className="absolute bottom-6 left-1/2 -translate-x-1/2 text-center w-full px-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7, duration: 0.6 }}
        >
          <p className="font-body text-[10px] xs:text-[11px] text-graphite/50 uppercase tracking-[0.2em]">
            Investment Intelligence Platform
          </p>
        </motion.div>
      </div>
    </div>
  );
}
