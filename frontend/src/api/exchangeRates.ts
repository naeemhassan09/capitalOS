import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type { ExchangeRate, ConvertResult, Currency } from '@/types';

export type ExchangeRateInput = Omit<ExchangeRate, 'id'>;

export function useExchangeRates() {
  return useQuery({
    queryKey: qk.exchangeRates,
    queryFn: () => api.get<ExchangeRate[]>('/exchange-rates'),
  });
}

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: qk.exchangeRates });
  qc.invalidateQueries({ queryKey: ['dashboard'] });
}

export function useCreateExchangeRate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<ExchangeRateInput>) =>
      api.post<ExchangeRate>('/exchange-rates', { json: payload }),
    onSuccess: () => invalidate(qc),
  });
}

export function useUpdateExchangeRate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Partial<ExchangeRateInput> & { id: string }) =>
      api.patch<ExchangeRate>(`/exchange-rates/${id}`, { json: payload }),
    onSuccess: () => invalidate(qc),
  });
}

export function useDeleteExchangeRate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/exchange-rates/${id}`),
    onSuccess: () => invalidate(qc),
  });
}

export function useConvert() {
  return useMutation({
    mutationFn: (params: { amount: number; from: Currency; to: Currency }) =>
      api.get<ConvertResult>('/exchange-rates/convert', { params }),
  });
}
