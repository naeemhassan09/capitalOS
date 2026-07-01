import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type { ScheduledCashflow, Transaction } from '@/types';

export type ScheduledCashflowInput = Omit<ScheduledCashflow, 'id' | 'next_due_date'>;

export interface MarkPaidInput {
  id: string;
  /** Required only when the cashflow has no account_id of its own. */
  account_id?: string;
  booking_date?: string;
}

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

export function useMarkCashflowPaid() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: MarkPaidInput) =>
      api.post<Transaction>(`/scheduled-cashflows/${id}/mark-paid`, { json: body }),
    onSuccess: () => {
      // Marking paid books a real transaction: the schedule advances/closes and
      // the account balance drops, so refresh balances and the dashboard too.
      qc.invalidateQueries({ queryKey: qk.scheduledCashflows });
      qc.invalidateQueries({ queryKey: qk.accounts.all });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      qc.invalidateQueries({ queryKey: ['transactions'] });
    },
  });
}
