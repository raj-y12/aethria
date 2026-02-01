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
        /* Locked palette — no new colors */
        oxford: '#002147',
        charcoal: '#2f333b',
        ivory: '#fcfcfc',
        bone: '#f2f4f8',
        mist: '#f2f4f8',
        /* Legacy (HomePage, LoadingAnimation — preserved) */
        canvas: '#fcfcfc',
        graphite: '#2f333b',
        heritage: '#F9F8F6',
        silver: '#D1D5DB',
        gold: '#B89F6F',
        'alert-crimson': '#E5484D',
        /* Loading: system calibration — dark field */
        'slate-dark': '#0f1218',
      },
      fontFamily: {
        display: ['"Libre Baskerville"', 'Georgia', 'serif'],
        body: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      borderRadius: { DEFAULT: '0', none: '0' },
      boxShadow: { DEFAULT: 'none', none: 'none' },
      maxWidth: { reading: '38rem' },
    },
  },
  plugins: [],
}
