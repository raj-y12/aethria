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
    <div className="flex min-h-[100dvh] w-full flex-col bg-paper">
      <motion.header
        className="flex shrink-0 items-center justify-end gap-4 border-b border-hairline bg-paper px-4 py-4 sm:px-8 sm:py-5 lg:px-10 xl:px-14"
        initial={reduceMotion ? false : { opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={transitionOrReduced(reduceMotion, {
          duration: tokens.motion.duration.medium,
          ease: tokens.motion.ease,
        })}
      >
        <span className="type-meta text-right uppercase tracking-[0.14em] text-oxford/50">
          Investment intelligence
        </span>
      </motion.header>

      <div className="flex min-h-0 flex-1 flex-col lg:min-h-[calc(100dvh-10rem)] lg:flex-row">
        {/* Oxford — ~70% width on large screens */}
        <motion.aside
          className="relative flex min-h-[38vh] shrink-0 flex-col justify-center bg-oxford px-6 py-10 text-paper sm:px-10 lg:min-h-0 lg:basis-[70%] lg:max-w-[70%] lg:flex-[0_0_70%] lg:py-16 xl:pl-20 xl:pr-12"
          initial={reduceMotion ? { x: 0, opacity: 1 } : { x: '-8%', opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={transitionOrReduced(reduceMotion, {
            duration: tokens.motion.duration.long,
            ease: tokens.motion.ease,
          })}
        >
          <div className="mx-auto w-full max-w-[32rem] lg:mx-0 lg:max-w-[36rem]">
            <motion.div
              initial={reduceMotion ? panelAnim : panelIn}
              animate={panelAnim}
              transition={transitionOrReduced(reduceMotion, {
                delay: 0.06,
                duration: tokens.motion.duration.medium,
                ease: tokens.motion.ease,
              })}
            >
              <div className="inline-flex w-full min-w-0 flex-col items-start" aria-live="polite">
                <AnimatePresence mode="wait">
                  {signedInGreeting ? (
                    <motion.div
                      key="hero-welcome"
                      className="inline-flex max-w-full flex-col items-stretch"
                      initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: -10 }}
                      transition={transitionOrReduced(reduceMotion, {
                        duration: tokens.motion.duration.medium,
                        ease: tokens.motion.ease,
                      })}
                    >
                      <h1 className="font-display max-w-full text-[clamp(1.35rem,3.4vw,2.65rem)] font-normal leading-[1.18] tracking-[-0.02em] text-paper">
                        {`Welcome back, ${signedInGreeting}.`}
                      </h1>
                      <motion.span
                        className="mt-2 block h-[3px] w-full max-w-full origin-left bg-paper"
                        initial={reduceMotion ? { scaleX: 1 } : { scaleX: 0 }}
                        animate={{ scaleX: 1 }}
                        transition={transitionOrReduced(reduceMotion, {
                          delay: 0.12,
                          duration: tokens.motion.duration.long,
                          ease: tokens.motion.ease,
                        })}
                        aria-hidden
                      />
                    </motion.div>
                  ) : (
                    <motion.div
                      key="hero-brand"
                      className="inline-flex flex-col items-start"
                      initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: -10 }}
                      transition={transitionOrReduced(reduceMotion, {
                        duration: tokens.motion.duration.medium,
                        ease: tokens.motion.ease,
                      })}
                    >
                      <h1 className="flex flex-wrap items-baseline gap-0 font-display text-[clamp(2rem,5vw,3.5rem)] font-normal leading-[1.1] tracking-[-0.02em] text-paper">
                        <span className="inline-flex flex-col items-stretch self-start">
                          <span className="inline-block w-max">A</span>
                          <motion.span
                            className="mt-2 block h-[3px] w-full origin-left bg-paper"
                            initial={reduceMotion ? { scaleX: 1 } : { scaleX: 0 }}
                            animate={{ scaleX: 1 }}
                            transition={transitionOrReduced(reduceMotion, {
                              delay: 0.28,
                              duration: tokens.motion.duration.long,
                              ease: tokens.motion.ease,
                            })}
                            aria-hidden
                          />
                        </span>
                        <span>ethria</span>
                      </h1>
                    </motion.div>
                  )}
                </AnimatePresence>
                <AnimatePresence mode="wait">
                  <motion.p
                    key={signedInGreeting ? 'sub-success' : 'sub-tagline'}
                    initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: -6 }}
                    transition={transitionOrReduced(reduceMotion, {
                      delay: signedInGreeting ? 0.08 : 0,
                      duration: tokens.motion.duration.medium,
                      ease: tokens.motion.ease,
                    })}
                    className="mt-6 max-w-[26rem] font-display text-[clamp(1.05rem,2.2vw,1.25rem)] italic leading-relaxed text-paper/70"
                  >
                    {signedInGreeting ? 'Entering your workspace…' : 'Judgment at institutional standard.'}
                  </motion.p>
                </AnimatePresence>
              </div>
            </motion.div>
          </div>
        </motion.aside>

        {/* Paper — ~30% */}
        <motion.section
          className="flex flex-1 flex-col justify-center px-6 py-10 sm:px-10 lg:min-w-0 lg:basis-[30%] lg:max-w-[30%] lg:flex-[0_0_30%] lg:py-16 xl:pr-16"
          data-login-page
          initial={reduceMotion ? panelAnim : panelIn}
          animate={panelAnim}
          transition={transitionOrReduced(reduceMotion, {
            delay: 0.12,
            duration: tokens.motion.duration.medium,
            ease: tokens.motion.ease,
          })}
        >
          <div className="mx-auto w-full max-w-[min(100%,17.5rem)] font-mono uppercase tracking-[0.1em]">
            <p className="mb-5 inline-block border border-oxford/15 bg-paper px-2 py-1.5 text-[10px] leading-normal text-oxford/50">
              Secure access
            </p>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                void handleSubmit();
              }}
              className="flex flex-col gap-0"
              noValidate
              aria-label="Sign in"
            >
              <div className="flex flex-col gap-4">
                <input
                  type="text"
                  autoComplete="username"
                  placeholder="Username or email"
                  aria-label="Username or email"
                  value={username}
                  disabled={signedInGreeting !== null}
                  onChange={(e) => setUsername(e.target.value)}
                  onKeyDown={(e) => handleKeyDown(e, 'username')}
                  className="w-full min-h-[44px] touch-manipulation border-0 border-b-[0.5px] border-oxford/25 bg-transparent pb-0.5 pt-2 font-mono text-[11px] leading-[1.45] text-oxford outline-none placeholder:text-oxford/35 btn-interaction disabled:cursor-not-allowed disabled:opacity-40"
                />
                <input
                  ref={passwordRef}
                  type="password"
                  autoComplete="current-password"
                  placeholder="Password"
                  aria-label="Password"
                  value={password}
                  disabled={signedInGreeting !== null}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => handleKeyDown(e, 'password')}
                  className="w-full min-h-[44px] touch-manipulation border-0 border-b-[0.5px] border-oxford/25 bg-transparent pb-0.5 pt-2 font-mono text-[11px] leading-[1.45] text-oxford outline-none placeholder:text-oxford/35 btn-interaction disabled:cursor-not-allowed disabled:opacity-40"
                />
              </div>

              <style>{`
                [data-login-page] input::placeholder {
                  font-family: "Space Mono", ui-monospace, monospace;
                  font-size: 10px;
                  line-height: 1.45;
                  font-weight: 400;
                  text-transform: uppercase;
                  letter-spacing: 0.1em;
                }
              `}</style>

              {error && (
                <motion.p
                  className="mt-3 text-[10px] leading-snug text-escalation"
                  role="alert"
                  initial={reduceMotion ? panelAnim : { opacity: 0, y: 6 }}
                  animate={panelAnim}
                  transition={transitionOrReduced(reduceMotion, {
                    duration: tokens.motion.duration.short,
                    ease: tokens.motion.ease,
                  })}
                >
                  {error}
                </motion.p>
              )}

              <div className="mt-7">
                <button
                  type="submit"
                  disabled={loading || signedInGreeting !== null}
                  className="flex min-h-[44px] w-full cursor-pointer items-center justify-center rounded-none border-0 bg-oxford px-4 py-2.5 font-mono text-[10px] leading-none tracking-[0.14em] text-paper hover:bg-oxford/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/45 focus-visible:ring-offset-2 focus-visible:ring-offset-paper disabled:cursor-not-allowed disabled:opacity-50 btn-interaction"
                  aria-busy={loading || signedInGreeting !== null}
                >
                  {signedInGreeting ? 'Redirecting…' : loading ? 'Signing in…' : 'Log in'}
                </button>
              </div>
            </form>
          </div>
        </motion.section>
      </div>

      <motion.footer
        className="flex min-h-[4.75rem] shrink-0 items-center justify-center border-t border-hairline bg-paper px-4 py-5 sm:min-h-[5.25rem] sm:px-8 sm:py-6 lg:px-10"
        initial={reduceMotion ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={transitionOrReduced(reduceMotion, {
          delay: 0.2,
          duration: tokens.motion.duration.medium,
          ease: tokens.motion.ease,
        })}
      >
        <p className="type-label-tab w-full text-center text-oxford/40">
          Versioned pipeline · Human-in-the-loop escalations · Immutable audit trail
        </p>
      </motion.footer>
    </div>
  );
}
