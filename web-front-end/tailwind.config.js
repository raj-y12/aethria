/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        oxford: '#001433',
        paper: '#f4f1ea',
        paperDeep: '#e7e0d4',
        'paper-bright': '#f8f5ee',
        ivory: '#f4f1ea',
        canvas: '#f4f1ea',
        mist: '#f2f4f8',
        charcoal: '#26313f',
        graphite: '#001433',
        escalation: '#8f4a32',
        gold: '#a88a5e',
        'gold-soft': 'rgba(168, 138, 94, 0.35)',
      },
      fontFamily: {
        display: ['"Playfair Display"', 'Georgia', 'serif'],
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
