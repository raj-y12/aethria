import { useEffect, useState } from 'react';
import type { Settings } from '../api/settings';
import {
  FUND_CONFIG_EVENT,
  clearFundConfiguration,
  loadFundConfiguration,
  saveFundConfiguration,
  type FundConfiguration,
} from '../lib/fundConfiguration';

export function useFundConfiguration(settings?: Settings | null) {
  const [configuration, setConfiguration] = useState<FundConfiguration>(() => loadFundConfiguration(settings));

  useEffect(() => {
    setConfiguration(loadFundConfiguration(settings));
  }, [settings]);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const handleUpdate = (event: Event) => {
      const custom = event as CustomEvent<FundConfiguration>;
      setConfiguration(custom.detail ?? loadFundConfiguration(settings));
    };
    window.addEventListener(FUND_CONFIG_EVENT, handleUpdate);
    return () => window.removeEventListener(FUND_CONFIG_EVENT, handleUpdate);
  }, [settings]);

  const save = (next: FundConfiguration) => {
    const saved = saveFundConfiguration(next);
    setConfiguration(saved);
    return saved;
  };

  const reset = () => {
    const next = clearFundConfiguration(settings);
    setConfiguration(next);
    return next;
  };

  return { configuration, setConfiguration, save, reset };
}
