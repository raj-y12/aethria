/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "../packages/product-chrome/src/**/*.{js,ts,jsx,tsx}",
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
        oxford: '#0a1629',
        paper: '#D9D7D4',
        /** Darker paper — WorkGrid selected row, etc. See --color-paper-deep */
        paperDeep: 'var(--color-paper-deep)',
        'paper-bright': '#E1DFDC',
        ivory: '#D9D7D4',
        canvas: '#D9D7D4',
        charcoal: '#1c2836',
        mist: '#E1DFDC',
        /** Legacy alias — same family as oxford (avoid cool neutral ink). */
        graphite: '#0a1629',
        /** Structural hairlines — prefer over raw oxford/[0.06] in new code. */
        hairline: 'rgba(10, 22, 41, 0.06)',
        'hairline-strong': 'rgba(10, 22, 41, 0.12)',
        /** Inputs, fields, subtle dividers. */
        'field-border': 'rgba(10, 22, 41, 0.15)',
        'field-border-strong': 'rgba(10, 22, 41, 0.20)',
        /** On-demand lookup origin chip — semantic, not raw hex in components. */
        lookup: {
          DEFAULT: '#8C7A4E',
          surface: '#D6D0BE',
          ink: '#2C2514',
        },
        /** Escalation / human-attention only — matches tokens.color.accent. */
        escalation: '#6E2A3C',
        /** Escalation on dark (oxford) chrome — same hue, lifted for contrast. */
        'escalation-bright': '#BF7583',
        /** Wordmark dot — verdigris; not for status semantics. */
        'brand-mark': '#3d6b5e',
        'brand-mark-inverse': '#7aab9a',
        /** Validation strip: same as paper (palette whitelist). */
        warning: '#D9D7D4',
        /** See :root --color-register-tint */
        registerTint: 'var(--color-register-tint)',
        /** Judgment-surface layering — maps to tokens.surface + index.css */
        'surface-canvas': 'var(--surface-canvas)',
        'surface-raised': 'var(--surface-raised)',
        'surface-recessed': 'var(--surface-recessed)',
        'surface-selected': 'var(--surface-selected)',
      },
      fontFamily: {
        display: ['"Playfair Display"', 'Georgia', 'serif'],
        wordmark: ['"Playfair Display"', 'Georgia', 'serif'],
        // Figtree Variable is the canonical app UI font — matches web-front-end warmth.
        sans: ['"Figtree Variable"', 'system-ui', '-apple-system', 'sans-serif'],
        body: ['"Figtree Variable"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"Space Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      /**
       * Type scale — golden ratio (φ = 1.618034), anchored at 14px.
       * body 14px → title 23px (×φ) → hero 37px (×φ²).
       * Pair with lineHeight and letterSpacing tokens below.
       */
      fontSize: {
        'type-meta':   ['10px', { lineHeight: '1.5', letterSpacing: '0.12em' }],
        'type-tab':    ['10px', { lineHeight: '1.5', letterSpacing: '0.14em' }],
        'type-label':  ['11px', { lineHeight: '1.5', letterSpacing: '0.12em' }],
        'type-sm':     ['13px', { lineHeight: '1.5' }],
        'type-body':   ['14px', { lineHeight: '1.5' }],
        'type-title':  ['23px', { lineHeight: '1.382', letterSpacing: '-0.02em' }],
        'type-hero':   ['37px', { lineHeight: '1.15',  letterSpacing: '-0.02em' }],
      },
      lineHeight: {
        phi: '1.618034',    // retained for legacy; prefer 1.5 for dense UI
        title: '1.382',     // 2 − 1/φ
        hero: '1.15',       // display / hero (tighter for large Playfair)
        label: '1.5',       // mono labels
      },
      letterSpacing: {
        tight:  '-0.02em',  // titles and hero
        label:  '0.12em',   // section labels (Space Mono)
        tab:    '0.14em',   // tab labels (Space Mono)
        badge:  '0.08em',   // badge/chip text
      },
      borderRadius: { DEFAULT: '0', none: '0' },
      boxShadow: { DEFAULT: 'none', none: 'none' },
      maxWidth: { reading: '38rem' },
      transitionProperty: {
        interactive: 'background-color, border-color, color, transform',
      },
      transitionDuration: {
        DEFAULT: '150ms',
        fast: '100ms',
        slow: '250ms',
      },
      transitionTimingFunction: {
        DEFAULT: 'cubic-bezier(0, 0, 0.2, 1)', // ease-out
      },
      /**
       * Golden ratio spacing scale — Fibonacci sequence, each step × φ ≈ next.
       * Use as: p-phi-4, gap-phi-5, mt-phi-6, etc.
       * CSS vars: --space-1 … --space-9 (set in index.css :root).
       */
      spacing: {
        'phi-1': 'var(--space-1)',
        'phi-2': 'var(--space-2)',
        'phi-3': 'var(--space-3)',
        'phi-4': 'var(--space-4)',
        'phi-5': 'var(--space-5)',
        'phi-6': 'var(--space-6)',
        'phi-7': 'var(--space-7)',
        'phi-8': 'var(--space-8)',
        'phi-9': 'var(--space-9)',
      },
    },
  },
  plugins: [],
}
