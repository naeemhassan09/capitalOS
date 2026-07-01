import { useQuery } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type {
  Dashboard,
  CashflowProjection,
  CashflowScenario,
  CashflowHorizon,
} from '@/types';

export function useDashboard() {
  return useQuery({
    queryKey: qk.dashboard.summary,
    queryFn: () => api.get<Dashboard>('/dashboard'),
    staleTime: 15_000,
  });
}

export function useCashflowProjection(scenario: CashflowScenario, horizon: CashflowHorizon) {
  return useQuery({
    queryKey: qk.dashboard.cashflow(scenario, horizon),
    queryFn: () =>
      api.get<CashflowProjection>('/dashboard/cashflow', {
        params: { scenario, horizon },
      }),
    placeholderData: (prev) => prev,
  });
}
