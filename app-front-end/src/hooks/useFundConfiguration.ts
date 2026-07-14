import { useEffect, useRef, useState } from 'react';
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
  const settingsRef = useRef(settings);
  settingsRef.current = settings;
  const remoteConfigKey = JSON.stringify(settings?.fund_config ?? null);

  useEffect(() => {
    setConfiguration(loadFundConfiguration(settingsRef.current));
  }, [remoteConfigKey]);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const handleUpdate = (event: Event) => {
      const custom = event as CustomEvent<FundConfiguration>;
      setConfiguration(custom.detail ?? loadFundConfiguration(settingsRef.current));
    };
    window.addEventListener(FUND_CONFIG_EVENT, handleUpdate);
    return () => window.removeEventListener(FUND_CONFIG_EVENT, handleUpdate);
  }, []);

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
