/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        oxford: '#1d2d48',
        paper: '#e9e0d1',
        ivory: '#e9e0d1',
        canvas: '#e9e0d1',
        mist: '#f2f4f8',
        graphite: '#2f333b',
      },
      fontFamily: {
        display: ['"Cormorant Garamond"', 'Georgia', 'serif'],
        sans: ['"Instrument Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
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
