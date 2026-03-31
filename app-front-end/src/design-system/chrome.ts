/**
 * Institutional chrome — framed surfaces, hairlines, register fills.
 * Use with Tailwind; mirrors :root vars in index.css (e.g. --color-register-tint).
 */

export const chrome = {
  /** Primary framed panel: paper + oxford hairline. */
  frame: 'rounded-none border border-hairline bg-paper',
  /** Secondary lift (optional cards on paper). */
  frameRaised: 'rounded-none border border-hairline bg-paper-bright',
  hairlineB: 'border-b border-hairline',
  hairlineR: 'border-r border-hairline',
  /** Pipe strip header / WorkGrid selected row — use Tailwind bg-registerTint (CSS var). */
  registerTint: 'bg-registerTint',
} as const;
