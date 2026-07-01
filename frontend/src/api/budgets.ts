import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type { Budget, BudgetReport } from '@/types';

export interface BudgetCreateInput {
  category_id: string;
  amount: number;
}

export interface BudgetUpdateInput {
  amount?: number;
  active?: boolean;
}

export function useBudgets() {
  return useQuery({
    queryKey: qk.budgets.all,
    queryFn: () => api.get<Budget[]>('/budgets'),
  });
}

export function useBudgetReport(year: number, month: number) {
  return useQuery({
    queryKey: qk.budgets.report(year, month),
    queryFn: () =>
      api.get<BudgetReport>('/budgets/report', { params: { year, month } }),
    placeholderData: (prev) => prev,
  });
}

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  // Budget CRUD affects both the raw list and every month's report.
  qc.invalidateQueries({ queryKey: qk.budgets.all });
  qc.invalidateQueries({ queryKey: ['budgets', 'report'] });
}

export function useCreateBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: BudgetCreateInput) => api.post<Budget>('/budgets', { json: payload }),
    onSuccess: () => invalidate(qc),
  });
}

export function useUpdateBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: BudgetUpdateInput & { id: string }) =>
      api.patch<Budget>(`/budgets/${id}`, { json: payload }),
    onSuccess: () => invalidate(qc),
  });
}

export function useDeleteBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/budgets/${id}`),
    onSuccess: () => invalidate(qc),
  });
}
