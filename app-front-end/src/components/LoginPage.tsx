import { useState, useCallback, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router';
import { useSignIn, useUser, useClerk } from '@clerk/react-router';
import { tokens } from '../design-system/tokens';

const OXford = '#002147';
const PAPER = '#F2F0EA';

export default function LoginPage() {
  const navigate = useNavigate();
  const { isLoaded, isSignedIn } = useUser();
  const { signIn } = useSignIn();
  const { setActive } = useClerk();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const passwordRef = useRef<HTMLInputElement>(null);
  const hasRedirectedRef = useRef(false);

  // Client-side redirect when already signed in (no full page reload — prevents reload loop)
  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    if (hasRedirectedRef.current) return;
    hasRedirectedRef.current = true;
    navigate('/v1', { replace: true });
  }, [isLoaded, isSignedIn, navigate]);

  const handleSubmit = useCallback(async (e?: React.MouseEvent) => {
    e?.preventDefault();
    if (loading) return;
    setError(null);
    setLoading(true);
    const trimmedUsername = username.trim();
    const trimmedPassword = password;
    if (!trimmedUsername || !trimmedPassword) {
      setError('Please enter both username and password.');
      setLoading(false);
      return;
    }
    if (!signIn) {
      setError('Sign-in is not ready. Please refresh the page and try again.');
      setLoading(false);
      return;
    }
    if (isSignedIn) {
      setLoading(false);
      navigate('/v1', { replace: true });
      return;
    }
    try {
      const result = await signIn.password({
        identifier: trimmedUsername,
        password: trimmedPassword,
      });

      if (result.error) {
        const msg = result.error.message ?? '';
        if (msg.toLowerCase().includes('already signed in') || (result.error as any)?.code === 'session_exists') {
          navigate('/v1', { replace: true });
          return;
        }
        setError(typeof result.error.message === 'string' ? result.error.message : 'Invalid username or password.');
        return;
      }

      if (signIn.status === 'complete') {
        if (typeof signIn.finalize === 'function') {
          await signIn.finalize();
        } else if (setActive && (signIn as any).createdSessionId) {
          await setActive({ session: (signIn as any).createdSessionId });
        }
        // Full-page navigation so the app reloads with the new session; avoids Clerk state not updating in time
        window.location.replace('/v1');
        return;
      }

      setError('Sign-in could not be completed. Please try again.');
    } catch (err: any) {
      const msg = (Array.isArray(err?.errors) && err.errors[0]?.message)
        ? String(err.errors[0].message)
        : err?.message ? String(err.message) : '';
      if (msg.toLowerCase().includes('already signed in') || msg.toLowerCase().includes('session_exists')) {
        navigate('/v1', { replace: true });
        return;
      }
      setError(Array.isArray(err?.errors) && err.errors[0]?.message ? String(err.errors[0].message) : err?.message ? String(err.message) : 'Something went wrong. Please try again.');
      setPassword('');
      passwordRef.current?.focus();
    } finally {
      setLoading(false);
    }
  }, [loading, username, password, signIn, navigate, isSignedIn, setActive]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, field: 'username' | 'password') => {
      if (e.key === 'Enter') {
        if (field === 'username') passwordRef.current?.focus();
        else void handleSubmit();
      }
    },
    [handleSubmit],
  );

  if (!isLoaded) {
    return null;
  }

  return (
    <div
      className="w-full flex flex-col items-center justify-center relative bg-paper min-h-[100dvh]"
      style={{ backgroundColor: PAPER }}
    >
      {/* Centered column — padding bottom so fixed footer doesn't overlap on small screens */}
      <div className="w-full max-w-[380px] flex flex-col items-center px-4 sm:px-6 flex-1 justify-center pb-28 sm:pb-0">
        {/* 1. Wordmark block — wrapper inline-block so underline matches wordmark width; responsive size on mobile */}
        <div className="inline-flex flex-col items-center">
          <motion.h1
            className="type-hero font-bold text-oxford"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: tokens.motion.duration.medium, ease: tokens.motion.ease }}
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
            transition={{ delay: 0.25, duration: tokens.motion.duration.long, ease: tokens.motion.ease }}
          />
        </div>

        {/* 2. Subtitle */}
        <motion.p
          className="type-label-tab text-oxford/40 mt-4"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35, duration: tokens.motion.duration.medium, ease: tokens.motion.ease }}
        >
          INVESTMENT INTELLIGENCE
        </motion.p>

        {/* 3. Custom Clerk-powered sign-in form (username + password) */}
        <div className="w-full max-w-[380px]" style={{ marginTop: '48px' }} data-login-page>
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: tokens.motion.duration.medium, ease: tokens.motion.ease }}
          >
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void handleSubmit();
              }}
              style={{ display: 'flex', flexDirection: 'column', gap: 0 }}
              noValidate
            >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <input
                type="text"
                autoComplete="username"
                placeholder="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onKeyDown={(e) => handleKeyDown(e, 'username')}
                className="w-full bg-transparent outline-none min-h-[44px] touch-manipulation type-body text-oxford/80 border-0 border-b border-oxford/25 pb-2.5 focus:border-oxford/25 focus-visible:ring-0 btn-interaction"
              />
              <input
                ref={passwordRef}
                type="password"
                autoComplete="current-password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => handleKeyDown(e, 'password')}
                className="w-full bg-transparent outline-none min-h-[44px] touch-manipulation type-body text-oxford/80 border-0 border-b border-oxford/25 pb-2.5 focus:border-oxford/25 focus-visible:ring-0 btn-interaction"
              />
            </div>

            {/* Placeholder styling scoped to this block */}
            <style>{`
              [data-login-page] input::placeholder {
                color: rgba(0, 33, 71, 0.25);
                font-family: Inter, system-ui, sans-serif;
                font-size: 14px;
                font-weight: 400;
              }
            `}</style>

            {/* Error state */}
            {error && (
              <motion.p
                className="type-label-section text-oxford/60 mt-3"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: tokens.motion.duration.short, ease: tokens.motion.ease }}
              >
                {error}
              </motion.p>
            )}

            {/* Submit button */}
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.65, duration: tokens.motion.duration.medium, ease: tokens.motion.ease }}
              style={{ marginTop: '32px' }}
            >
              <button
                type="button"
                disabled={loading}
                onClick={(e) => {
                  e.preventDefault();
                  void handleSubmit(e);
                }}
                className="w-full type-label-section h-11 bg-oxford text-paper border-0 cursor-pointer btn-interaction hover:opacity-90"
              >
                {loading ? (
                  <span className="inline-flex items-center justify-center gap-1 type-label-section">
                    <motion.span
                      animate={{ opacity: [0.4, 1, 0.4] }}
                      transition={{ repeat: Infinity, duration: tokens.motion.duration.short, ease: tokens.motion.ease }}
                    >
                      .
                    </motion.span>
                    <motion.span
                      animate={{ opacity: [0.4, 1, 0.4] }}
                      transition={{ repeat: Infinity, duration: tokens.motion.duration.short, ease: tokens.motion.ease, delay: 0.15 }}
                    >
                      .
                    </motion.span>
                    <motion.span
                      animate={{ opacity: [0.4, 1, 0.4] }}
                      transition={{ repeat: Infinity, duration: tokens.motion.duration.short, ease: tokens.motion.ease, delay: 0.3 }}
                    >
                      .
                    </motion.span>
                  </span>
                ) : (
                  'LOG IN'
                )}
              </button>
            </motion.div>
            </form>
          </motion.div>
        </div>
      </div>

      {/* 5. Footer — fixed to viewport bottom; safe-area for notched devices */}
      <motion.footer
        className="fixed left-0 right-0 flex justify-center px-4 text-center"
        style={{ bottom: 'max(32px, env(safe-area-inset-bottom))' }}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.85, duration: tokens.motion.duration.medium, ease: tokens.motion.ease }}
      >
        <p className="type-meta text-oxford/25">
          AETHRIA · INVESTMENT INTELLIGENCE PLATFORM
        </p>
      </motion.footer>
    </div>
  );
}
