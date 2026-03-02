import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { tokens } from '../design-system/tokens';

const LOGIN_USERNAME = 'raj';
const LOGIN_PASSWORD = '#Mukesh123';

interface EnterSystemPageProps {
  onEnter: () => void;
}

const EASE = [0.16, 1, 0.3, 1] as const;

const inputCls =
  'w-full max-w-[16rem] bg-transparent border-0 border-b border-ivory/40 font-mono text-[13px] text-ivory placeholder:text-ivory/40 py-2.5 outline-none focus:border-ivory transition-colors duration-200 rounded-none';

export default function EnterSystemPage({ onEnter }: EnterSystemPageProps) {
  const [isExiting, setIsExiting] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (username.trim() === LOGIN_USERNAME && password === LOGIN_PASSWORD) {
      setIsExiting(true);
    } else {
      setError('Invalid username or password.');
    }
  };

  const handleExitComplete = () => {
    onEnter();
  };

  return (
    <div className="min-h-screen w-full flex flex-col items-center overflow-hidden bg-oxford">
      <div className="flex-1 w-full flex flex-col items-center justify-center px-6 sm:px-8 lg:px-10">
        <div className="w-full max-w-2xl flex flex-col items-center text-center">
          <AnimatePresence mode="wait" onExitComplete={handleExitComplete}>
            {!isExiting && (
              <motion.div
                key="content"
                className="flex flex-col items-center text-center w-full"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0, y: -12 }}
                transition={{ duration: tokens.motion.duration.medium, ease: tokens.motion.ease }}
              >
                <motion.h1
                  className="font-display font-bold text-ivory tracking-[-0.05em] mb-8"
                  style={{
                    fontSize: 'clamp(2rem, 8vw, 4rem)',
                    lineHeight: 1.1,
                  }}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 1.5, duration: 0.8, ease: EASE }}
                >
                  <span className="relative inline-block mr-0.5">
                    A
                    <motion.span
                      className="absolute bottom-0 left-0 right-0 h-[0.06em] bg-ivory"
                      initial={{ scaleX: 0 }}
                      animate={{ scaleX: 1 }}
                      transition={{ delay: 2.5, duration: 0.5, ease: EASE }}
                    />
                  </span>
                  ethria
                </motion.h1>

                <motion.p
                  className="font-mono text-[10px] text-ivory/80 uppercase mb-8 sm:mb-10"
                  style={{ letterSpacing: '0.22em' }}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 1.0, duration: 0.5, ease: EASE }}
                >
                  Intelligent investment discovery and evaluation system
                </motion.p>

                <motion.form
                  onSubmit={handleSubmit}
                  className="flex flex-col items-center gap-4 w-full"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 1.2, duration: 0.5, ease: EASE }}
                >
                  <label className="sr-only" htmlFor="login-username">Username</label>
                  <input
                    id="login-username"
                    type="text"
                    autoComplete="username"
                    placeholder="Username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className={inputCls}
                  />
                  <label className="sr-only" htmlFor="login-password">Password</label>
                  <input
                    id="login-password"
                    type="password"
                    autoComplete="current-password"
                    placeholder="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={inputCls}
                  />
                  {error && (
                    <p className="font-mono text-[10px] text-ivory/80 uppercase" style={{ letterSpacing: '0.12em' }}>
                      {error}
                    </p>
                  )}
                  <button
                    type="submit"
                    className="font-mono text-[10px] uppercase text-ivory/80 hover:bg-paper hover:text-oxford border border-ivory/40 px-5 py-2.5 transition-colors duration-300 w-fit rounded-none mt-1"
                    style={{ letterSpacing: '0.22em' }}
                  >
                    Log in
                  </button>
                </motion.form>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
      <footer className="w-full py-4 flex justify-center">
        <motion.p
          className="font-mono text-[10px] text-ivory/60 uppercase"
          style={{ letterSpacing: '0.22em' }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.4, duration: 0.5, ease: EASE }}
        >
          Investment Intelligence Platform
        </motion.p>
      </footer>
    </div>
  );
}
