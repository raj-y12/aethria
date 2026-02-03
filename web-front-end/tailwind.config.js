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
        ivory: '#fcfcfc',
        canvas: '#fcfcfc',
        mist: '#f2f4f8',
        graphite: '#2f333b',
      },
      fontFamily: {
        display: ['"Libre Baskerville"', 'serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
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
