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
        /** Structural hairlines — prefer over raw oxford/[0.06] in new code. */
        hairline: 'rgba(0, 33, 71, 0.06)',
        'hairline-strong': 'rgba(0, 33, 71, 0.12)',
        /** Inputs, fields, subtle dividers. */
        'field-border': 'rgba(0, 33, 71, 0.15)',
        'field-border-strong': 'rgba(0, 33, 71, 0.20)',
        /** On-demand lookup origin chip — semantic, not raw hex in components. */
        lookup: {
          DEFAULT: '#B5893E',
          surface: '#E8D7B4',
          ink: '#3D2A12',
        },
        /** Escalation / human-attention only — matches tokens.color.accent. */
        escalation: '#7D2B3A',
        /** Decorative — aligned with web-front-end. */
        gold: '#b8976a',
        'gold-soft': 'rgba(184, 151, 106, 0.35)',
        /** Validation strip: same as paper (palette whitelist). */
        warning: '#F2F0EA',
        /** See :root --color-register-tint */
        registerTint: 'var(--color-register-tint)',
      },
      fontFamily: {
        display: ['"Libre Baskerville"', 'Georgia', 'serif'],
        cormorant: ['"Cormorant Garamond"', 'Georgia', 'serif'],
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
