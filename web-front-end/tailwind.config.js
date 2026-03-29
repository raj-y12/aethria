/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        oxford: '#002147',
        paper: '#f2f0ea',
        ivory: '#fcfcfc',
        canvas: '#fcfcfc',
        mist: '#f2f4f8',
        graphite: '#2f333b',
      },
      fontFamily: {
        display: ['"Cormorant Garamond"', 'Georgia', 'serif'],
        sans: ['"Instrument Sans"', 'system-ui', 'sans-serif'],
        mono: ['"Space Mono"', 'monospace'],
        wordmark: ['var(--font-wordmark)', 'Georgia', 'serif'],
      },
      borderRadius: {
        DEFAULT: '0',
        none: '0',
      },
      boxShadow: {
        DEFAULT: 'none',
        none: 'none',
      },
      maxWidth: {
        reading: '38rem',
      },
    },
  },
  plugins: [],
}
