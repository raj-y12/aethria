import { useState, useCallback, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router';
import { useSignIn, useUser, useClerk } from '@clerk/react-router';
import { tokens } from '../design-system/tokens';
import { transitionOrReduced } from '../design-system/motion';
import { usePrefersReducedMotion } from '../hooks';

function friendlyIdentifier(id: string): string {
  const t = id.trim();
  if (!t) return 'there';
  const at = t.indexOf('@');
  if (at > 0) return t.slice(0, at);
  return t.length > 36 ? `${t.slice(0, 33)}…` : t;
}

const REDIRECT_AFTER_MS = 2200;

export default function LoginPage() {
  const reduceMotion = usePrefersReducedMotion();
  const navigate = useNavigate();
  const { isLoaded, isSignedIn } = useUser();
  const { signIn } = useSignIn();
  const { setActive } = useClerk();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  /** When set, hero shows "Welcome back, …" then we redirect. */
  const [signedInGreeting, setSignedInGreeting] = useState<string | null>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const hasRedirectedRef = useRef(false);
  const redirectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Set before session activates so the isSignedIn effect cannot navigate away before the welcome beat. */
  const holdAutoRedirectForWelcomeRef = useRef(false);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    if (hasRedirectedRef.current) return;
    if (signedInGreeting !== null) return;
    if (holdAutoRedirectForWelcomeRef.current) return;
    hasRedirectedRef.current = true;
    navigate('/v1', { replace: true });
  }, [isLoaded, isSignedIn, navigate, signedInGreeting]);

  useEffect(() => {
    return () => {
      if (redirectTimerRef.current) clearTimeout(redirectTimerRef.current);
    };
  }, []);

  const handleSubmit = useCallback(
    async (e?: React.MouseEvent) => {
      e?.preventDefault();
      if (loading || signedInGreeting !== null) return;
      setError(null);
      setLoading(true);
      const trimmedUsername = username.trim();
      const trimmedPassword = password;
      let skipLoadingReset = false;

      if (!trimmedUsername || !trimmedPassword) {
        setError('Enter both username and password to continue.');
        setLoading(false);
        return;
      }
      if (!signIn) {
        setError('Sign-in is not ready. Refresh the page and try again.');
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
          if (
            msg.toLowerCase().includes('already signed in') ||
            (result.error as { code?: string }).code === 'session_exists'
          ) {
            navigate('/v1', { replace: true });
            return;
          }
          setError(
            typeof result.error.message === 'string'
              ? result.error.message
              : 'Invalid username or password.'
          );
          return;
        }

        if (signIn.status === 'complete') {
          const name = friendlyIdentifier(trimmedUsername);
          holdAutoRedirectForWelcomeRef.current = true;
          setSignedInGreeting(name);
          try {
            if (typeof signIn.finalize === 'function') {
              await signIn.finalize();
            } else if (setActive && (signIn as { createdSessionId?: string }).createdSessionId) {
              await setActive({ session: (signIn as { createdSessionId: string }).createdSessionId });
            }
          } catch {
            holdAutoRedirectForWelcomeRef.current = false;
            setSignedInGreeting(null);
            setError('Sign-in could not be completed. Please try again.');
            return;
          }
          skipLoadingReset = true;
          const delay = reduceMotion ? 600 : REDIRECT_AFTER_MS;
          redirectTimerRef.current = setTimeout(() => {
            holdAutoRedirectForWelcomeRef.current = false;
            window.location.replace('/v1');
          }, delay);
          return;
        }

        setError('Sign-in could not be completed. Please try again.');
      } catch (err: unknown) {
        const e = err as { errors?: { message?: string }[]; message?: string };
        const msg =
          Array.isArray(e?.errors) && e.errors[0]?.message
            ? String(e.errors[0].message)
            : e?.message
              ? String(e.message)
              : '';
        if (msg.toLowerCase().includes('already signed in') || msg.toLowerCase().includes('session_exists')) {
          navigate('/v1', { replace: true });
          return;
        }
        setError(
          Array.isArray(e?.errors) && e.errors[0]?.message
            ? String(e.errors[0].message)
            : e?.message
              ? String(e.message)
              : 'Something went wrong. Please try again.'
        );
        setPassword('');
        passwordRef.current?.focus();
      } finally {
        if (!skipLoadingReset) setLoading(false);
      }
    },
    [loading, signedInGreeting, username, password, signIn, navigate, isSignedIn, setActive, reduceMotion]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, field: 'username' | 'password') => {
      if (e.key === 'Enter') {
        if (field === 'username') passwordRef.current?.focus();
        else void handleSubmit();
      }
    },
    [handleSubmit]
  );

  if (!isLoaded) {
    return null;
  }

  const panelIn = reduceMotion
    ? { opacity: 1, y: 0 }
    : { opacity: 0, y: 14 };
  const panelAnim = { opacity: 1, y: 0 };

  return (
    <div className="flex flex-col items-center justify-center min-h-[100dvh] w-full bg-paper p-phi-6 overflow-hidden">
      <div className="relative w-full max-w-[48rem] flex flex-col items-center">
        {/* Structural Accent: The Vertical Spine */}
        <motion.div
          initial={reduceMotion ? { opacity: 1, scaleY: 1 } : { opacity: 0, scaleY: 0 }}
          animate={{ opacity: 1, scaleY: 1 }}
          transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
          className="absolute left-1/2 -ml-px top-[-20vh] bottom-[-20vh] w-[0.5px] bg-oxford/[0.08]"
          aria-hidden="true"
        />

        {/* Brand Monolith */}
        <div className="relative z-10 w-full mb-phi-9 flex flex-col items-center">
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1], delay: 0.25 }}
            className="type-meta uppercase tracking-[0.25em] text-oxford/30 mb-phi-3"
          >
            Confidential · Institutional Access
          </motion.p>

          <AnimatePresence mode="wait">
            {signedInGreeting ? (
              <motion.div
                key="welcome-header"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.98 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                className="flex flex-col items-center"
              >
                <h1 className="font-wordmark text-center text-[clamp(28px,5vw,56px)] font-normal text-oxford leading-[1.1] m-0">
                  Welcome back, {signedInGreeting}.
                </h1>
                <p className="type-body text-oxford/40 mt-phi-3 italic">
                  Entering workspace…
                </p>
              </motion.div>
            ) : (
              <motion.div
                key="brand-header"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay: 0.35 }}
                className="flex flex-col items-center"
              >
                <h1 className="font-wordmark text-center text-[clamp(44px,8vw,80px)] font-normal text-oxford leading-[0.9] m-0 tracking-normal">
                  Aethria
                </h1>
                <p className="type-meta uppercase tracking-[0.14em] text-oxford/35 mt-phi-4">
                  Deal flow operating system
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Auth Interface */}
        {!signedInGreeting && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: 0.55 }}
            className="relative z-10 w-full max-w-[280px]"
          >
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void handleSubmit();
              }}
              className="flex flex-col"
              noValidate
            >
              <div className="flex flex-col gap-phi-5 mb-phi-8">
                <div className="flex flex-col">
                  <input
                    type="text"
                    autoComplete="username"
                    placeholder="IDENTIFIER"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    onKeyDown={(e) => handleKeyDown(e, 'username')}
                    className="w-full bg-transparent border-0 border-b border-oxford/10 py-phi-3 font-mono text-[10px] text-oxford outline-none placeholder:text-oxford/20 focus:border-oxford/40 transition-colors tracking-widest"
                  />
                </div>

                <div className="flex flex-col">
                  <input
                    ref={passwordRef}
                    type="password"
                    autoComplete="current-password"
                    placeholder="CREDENTIAL"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onKeyDown={(e) => handleKeyDown(e, 'password')}
                    className="w-full bg-transparent border-0 border-b border-oxford/10 py-phi-3 font-mono text-[10px] text-oxford outline-none placeholder:text-oxford/20 focus:border-oxford/40 transition-colors tracking-widest"
                  />
                </div>
              </div>

              {error && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="type-meta text-[9px] text-escalation text-center mb-phi-6 uppercase tracking-widest opacity-80"
                >
                  {error}
                </motion.p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-phi-4 bg-oxford text-paper type-meta text-[10px] uppercase tracking-[0.2em] btn-interaction transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                {loading ? 'Authenticating…' : 'Establish Session'}
              </button>
            </form>
          </motion.div>
        )}

        {/* Footer Ledger */}
        <motion.footer
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 1 }}
          className="fixed bottom-0 left-0 w-full p-phi-6 flex justify-center pointer-events-none"
        >
          <div className="flex items-center gap-phi-4 opacity-25">
             <span className="type-meta text-[8px] uppercase tracking-[0.2em] text-oxford">
              Protocol 4.1
            </span>
            <div className="w-px h-2 bg-oxford/40" />
            <span className="type-meta text-[8px] uppercase tracking-[0.2em] text-oxford">
              Secure Perimeter
            </span>
          </div>
        </motion.footer>
      </div>
    </div>
  );
}
