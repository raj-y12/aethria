import { apiRequest } from './client';

export interface PortfolioPosition {
  position_id: string;
  opportunity_id: string;
  company_id: string;
  ruling_id: string;
  status: 'active' | 'exited' | 'written_off' | string;
  entry_rationale: string;
  investor_confidence: number;
  entered_at: string;
  canonical_name?: string;
  canonical_domain?: string | null;
  legacy_startup_id?: string | null;
}

export async function fetchPortfolioPositions(limit = 100): Promise<PortfolioPosition[]> {
  const result = await apiRequest<{ positions?: PortfolioPosition[] }>(`/api/portfolio/positions?limit=${limit}`);
  return Array.isArray(result.positions) ? result.positions : [];
}
