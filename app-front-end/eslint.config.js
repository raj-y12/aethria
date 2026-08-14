import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';

const browserGlobals = {
  AbortController: 'readonly',
  Blob: 'readonly',
  clearTimeout: 'readonly',
  console: 'readonly',
  CustomEvent: 'readonly',
  document: 'readonly',
  Event: 'readonly',
  fetch: 'readonly',
  File: 'readonly',
  FormData: 'readonly',
  Headers: 'readonly',
  IntersectionObserver: 'readonly',
  localStorage: 'readonly',
  navigator: 'readonly',
  performance: 'readonly',
  queueMicrotask: 'readonly',
  Request: 'readonly',
  Response: 'readonly',
  sessionStorage: 'readonly',
  setInterval: 'readonly',
  setTimeout: 'readonly',
  URL: 'readonly',
  URLSearchParams: 'readonly',
  window: 'readonly',
};

const nodeGlobals = {
  Buffer: 'readonly',
  globalThis: 'readonly',
  process: 'readonly',
};

export default [
  {
    ignores: ['dist/**', 'node_modules/**', 'screenshot/**', 'vite.screenshot.config.ts', 'demo/**', 'vite.demo.config.ts', 'e2e/**', 'playwright.config.ts'],
  },
  {
    files: ['src/**/*.{ts,tsx}', 'tests/**/*.ts', 'vite.config.ts'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaFeatures: { jsx: true },
        ecmaVersion: 2022,
        sourceType: 'module',
      },
      globals: browserGlobals,
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      'no-undef': 'off',
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': 'off',
      'react-hooks/rules-of-hooks': 'error',
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    files: ['tests/**/*.ts', 'vite.config.ts'],
    languageOptions: {
      globals: nodeGlobals,
    },
  },
];
