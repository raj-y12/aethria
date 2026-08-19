import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Copies text to the clipboard and reports a short-lived `copied` flag the
 * caller can use to swap a label to "Copied" before it reverts.
 */
export function useCopyToClipboard(resetMs = 1500) {
  const [copied, setCopied] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
  }, []);

  const copy = useCallback((text: string) => {
    if (!text || typeof navigator === 'undefined' || !navigator.clipboard) return;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setCopied(false), resetMs);
    }).catch(() => {
      // Clipboard permission denied or unavailable — no-op, nothing to recover.
    });
  }, [resetMs]);

  return { copied, copy };
}
