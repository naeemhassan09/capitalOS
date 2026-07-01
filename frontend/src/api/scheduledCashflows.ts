import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type { ScheduledCashflow } from '@/types';

export type ScheduledCashflowInput = Omit<ScheduledCashflow, 'id' | 'next_due_date'>;

export function useScheduledCashflows() {
  return useQuery({
    queryKey: qk.scheduledCashflows,
    queryFn: () => api.get<ScheduledCashflow[]>('/scheduled-cashflows'),
  });
}

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: qk.scheduledCashflows });
  qc.invalidateQueries({ queryKey: ['dashboard'] });
}

export function useCreateScheduledCashflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<ScheduledCashflowInput>) =>
      api.post<ScheduledCashflow>('/scheduled-cashflows', { json: payload }),
    onSuccess: () => invalidate(qc),
  });
}

export function useUpdateScheduledCashflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Partial<ScheduledCashflowInput> & { id: string }) =>
      api.patch<ScheduledCashflow>(`/scheduled-cashflows/${id}`, { json: payload }),
    onSuccess: () => invalidate(qc),
  });
}

export function useDeleteScheduledCashflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/scheduled-cashflows/${id}`),
    onSuccess: () => invalidate(qc),
  });
}
