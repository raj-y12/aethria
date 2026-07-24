/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "../packages/product-chrome/src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        oxford: '#0a1629',
        paper: '#d9d7d4',
        ivory: '#d9d7d4',
        canvas: '#d9d7d4',
        mist: '#f2f4f8',
        charcoal: '#26313f',
        escalation: '#8f4a32',
        accent: '#3d6b5e',
        'accent-strong': '#2f574c',
        'brand-mark': '#3d6b5e',
        'brand-mark-inverse': '#7aab9a',
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
