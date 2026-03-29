/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    /* Breakpoints: 480 / 768 / 1024 / 1440 — desktop source of truth */
    screens: {
      xs: '480px',
      sm: '640px',
      md: '768px',
      lg: '1024px',
      xl: '1280px',
      '2xl': '1440px',
    },
    extend: {
      colors: {
        oxford: '#002147',
        paper: '#F2F0EA',
        'paper-bright': '#faf8f4',
        charcoal: '#2f333b',
        ivory: '#FFFFFF',
        bone: '#f2f4f8',
        mist: '#f2f4f8',
        canvas: '#FFFFFF',
        graphite: '#2f333b',
        heritage: '#F9F8F6',
        silver: '#D1D5DB',
        /** Decorative only — aligned with web-front-end warm accent. */
        gold: '#b8976a',
        'gold-soft': 'rgba(184, 151, 106, 0.35)',
        'alert-crimson': '#E5484D',
        'slate-dark': '#0f1218',
        /** Validation strip: same as paper (palette whitelist). */
        warning: '#F2F0EA',
      },
      fontFamily: {
        display: ['"Libre Baskerville"', 'Georgia', 'serif'],
        sans: ['"Geist Sans"', 'system-ui', '-apple-system', 'sans-serif'],
        body: ['"Geist Sans"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"Space Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      borderRadius: { DEFAULT: '0', none: '0' },
      boxShadow: { DEFAULT: 'none', none: 'none' },
      maxWidth: { reading: '38rem' },
    },
  },
  plugins: [],
}
