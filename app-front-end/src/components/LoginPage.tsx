import { useState, useCallback, useRef } from 'react';
import { motion } from 'framer-motion';
import { tokens } from '../design-system/tokens';

const VALID_USERNAME = import.meta.env.VITE_AUTH_USERNAME ?? 'raj';
const VALID_PASSWORD = import.meta.env.VITE_AUTH_PASSWORD ?? '#Mukesh123';

const OXford = '#002147';
const PAPER = '#F2F0EA';
const EASE_UNDERLINE = [0.16, 1, 0.3, 1] as [number, number, number, number];

interface LoginPageProps {
  onSuccess: () => void;
}

export default function LoginPage({ onSuccess }: LoginPageProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);
  const passwordRef = useRef<HTMLInputElement>(null);

  const handleSubmit = useCallback(() => {
    setError(false);
    if (username.trim() === VALID_USERNAME && password === VALID_PASSWORD) {
      setLoading(true);
      sessionStorage.setItem('auth', 'true');
      const name = username.trim();
      sessionStorage.setItem('authUser', name.charAt(0).toUpperCase() + name.slice(1).toLowerCase());
      onSuccess();
      return;
    }
    setError(true);
    setPassword('');
    passwordRef.current?.focus();
  }, [username, password, onSuccess]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, field: 'username' | 'password') => {
      if (e.key === 'Enter') {
        if (field === 'username') passwordRef.current?.focus();
        else handleSubmit();
      }
    },
    [handleSubmit]
  );

  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center relative bg-paper" style={{ backgroundColor: PAPER }}>
      {/* Centered column */}
      <div className="w-full max-w-[380px] flex flex-col items-center px-6 flex-1 justify-center">
        {/* 1. Wordmark block — wrapper inline-block so underline matches wordmark width */}
        <div className="inline-flex flex-col items-center">
          <motion.h1
            className="font-display text-oxford"
            style={{
              fontFamily: tokens.font.display,
              fontSize: '48px',
              fontWeight: 400,
              lineHeight: 1,
            }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4 }}
          >
            Aethria
          </motion.h1>
          <motion.span
            className="block h-px w-full origin-left"
            style={{
              backgroundColor: OXford,
              marginTop: '6px',
            }}
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ delay: 0.3, duration: 0.6, ease: EASE_UNDERLINE }}
          />
        </div>

        {/* 2. Subtitle */}
        <motion.p
          className="font-mono uppercase"
          style={{
            fontFamily: tokens.font.mono,
            fontSize: '10px',
            letterSpacing: '0.2em',
            color: 'rgba(0, 33, 71, 0.45)',
            marginTop: '16px',
          }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5, duration: 0.3 }}
        >
          INVESTMENT INTELLIGENCE
        </motion.p>

        {/* 3. Form fields + 4. Button — no form element */}
        <div className="w-full max-w-[380px]" style={{ marginTop: '48px' }} data-login-page>
          <motion.div
            style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.65, duration: 0.25 }}
          >
            <input
              type="text"
              autoComplete="username"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={(e) => handleKeyDown(e, 'username')}
              className="w-full bg-transparent outline-none"
              style={{
                height: '44px',
                border: 'none',
                borderBottom: '1px solid rgba(0, 33, 71, 0.15)',
                padding: '0 0 10px 0',
                fontFamily: 'Inter, system-ui, sans-serif',
                fontSize: '14px',
                fontWeight: 400,
                color: 'rgba(0, 33, 71, 0.9)',
                transition: 'border-color 200ms ease',
              }}
              onFocus={(e) => {
                e.target.style.borderBottomColor = 'rgba(0, 33, 71, 0.6)';
              }}
              onBlur={(e) => {
                e.target.style.borderBottomColor = 'rgba(0, 33, 71, 0.15)';
              }}
            />
          </motion.div>
          <motion.div
            style={{ marginTop: '20px' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.75, duration: 0.25 }}
          >
            <input
              ref={passwordRef}
              type="password"
              autoComplete="current-password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => handleKeyDown(e, 'password')}
              className="w-full bg-transparent outline-none"
              style={{
                height: '44px',
                border: 'none',
                borderBottom: '1px solid rgba(0, 33, 71, 0.15)',
                padding: '0 0 10px 0',
                fontFamily: 'Inter, system-ui, sans-serif',
                fontSize: '14px',
                fontWeight: 400,
                color: 'rgba(0, 33, 71, 0.9)',
                transition: 'border-color 200ms ease',
              }}
              onFocus={(e) => {
                e.target.style.borderBottomColor = 'rgba(0, 33, 71, 0.6)';
              }}
              onBlur={(e) => {
                e.target.style.borderBottomColor = 'rgba(0, 33, 71, 0.15)';
              }}
            />
          </motion.div>

          {/* Placeholder: Inter 14px, oxford 30% — scoped to this section */}
          <style>{`
            [data-login-page] input::placeholder {
              color: rgba(0, 33, 71, 0.3);
              font-family: Inter, system-ui, sans-serif;
              font-size: 14px;
              font-weight: 400;
            }
          `}</style>

          {/* Error state */}
          {error && (
            <motion.p
              className="font-mono uppercase"
              style={{
                fontFamily: tokens.font.mono,
                fontSize: '9px',
                letterSpacing: '0.15em',
                color: 'rgba(0, 33, 71, 0.7)',
                marginTop: '12px',
              }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2 }}
            >
              INVALID CREDENTIALS
            </motion.p>
          )}

          {/* 4. Login button */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.85, duration: 0.25 }}
            style={{ marginTop: '32px' }}
          >
            <button
              type="button"
              onClick={handleSubmit}
              disabled={loading}
              className="w-full font-mono uppercase outline-none cursor-pointer transition-colors disabled:opacity-70"
              style={{
                height: '44px',
                background: OXford,
                color: PAPER,
                fontFamily: tokens.font.mono,
                fontSize: '11px',
                letterSpacing: '0.15em',
                border: 'none',
                transitionDuration: '150ms',
                transitionTimingFunction: 'ease',
              }}
              onMouseEnter={(e) => {
                if (!loading) e.currentTarget.style.backgroundColor = 'rgba(0, 33, 71, 0.85)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = OXford;
              }}
              onMouseDown={(e) => {
                if (!loading) e.currentTarget.style.opacity = '0.7';
              }}
              onMouseUp={(e) => {
                e.currentTarget.style.opacity = '1';
              }}
            >
              {loading ? (
                <span className="inline-flex items-center justify-center gap-1" style={{ fontFamily: tokens.font.mono }}>
                  <motion.span animate={{ opacity: [0.3, 1, 0.3] }} transition={{ repeat: Infinity, duration: 0.6 }}>.</motion.span>
                  <motion.span animate={{ opacity: [0.3, 1, 0.3] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0.2 }}>.</motion.span>
                  <motion.span animate={{ opacity: [0.3, 1, 0.3] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0.4 }}>.</motion.span>
                </span>
              ) : (
                'LOG IN'
              )}
            </button>
          </motion.div>
        </div>
      </div>

      {/* 5. Footer — fixed to viewport bottom */}
      <motion.footer
        className="fixed left-0 right-0 flex justify-center"
        style={{ bottom: '32px' }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.9, duration: 0.3 }}
      >
        <p
          className="font-mono uppercase"
          style={{
            fontFamily: tokens.font.mono,
            fontSize: '9px',
            letterSpacing: '0.15em',
            color: 'rgba(0, 33, 71, 0.25)',
          }}
        >
          AETHRIA · INVESTMENT INTELLIGENCE PLATFORM
        </p>
      </motion.footer>
    </div>
  );
}
