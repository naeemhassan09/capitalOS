import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type { Holding, HoldingValuation } from '@/types';

export type HoldingInput = Omit<Holding, 'id' | 'latest_valuation' | 'valuation_date'> & {
  latest_valuation?: number | null;
  valuation_date?: string | null;
};

export function useHoldings() {
  return useQuery({
    queryKey: qk.holdings,
    queryFn: () => api.get<Holding[]>('/holdings'),
  });
}

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: qk.holdings });
  qc.invalidateQueries({ queryKey: qk.dashboard.summary });
}

export function useCreateHolding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<HoldingInput>) => api.post<Holding>('/holdings', { json: payload }),
    onSuccess: () => invalidate(qc),
  });
}

export function useUpdateHolding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Partial<HoldingInput> & { id: string }) =>
      api.patch<Holding>(`/holdings/${id}`, { json: payload }),
    onSuccess: () => invalidate(qc),
  });
}

export function useDeleteHolding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/holdings/${id}`),
    onSuccess: () => invalidate(qc),
  });
}

export function useAddValuation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: HoldingValuation & { id: string }) =>
      api.post<Holding>(`/holdings/${id}/valuations`, { json: payload }),
    onSuccess: () => invalidate(qc),
  });
}
