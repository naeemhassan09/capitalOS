import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type { Rule, RuleTestResult } from '@/types';

export type RuleInput = Omit<Rule, 'id' | 'created_at'>;

export function useRules() {
  return useQuery({
    queryKey: qk.rules,
    queryFn: () => api.get<Rule[]>('/rules'),
  });
}

export function useCreateRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<RuleInput>) => api.post<Rule>('/rules', { json: payload }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.rules }),
  });
}

export function useUpdateRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Partial<RuleInput> & { id: string }) =>
      api.patch<Rule>(`/rules/${id}`, { json: payload }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.rules }),
  });
}

export function useDeleteRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/rules/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.rules }),
  });
}

export function useTestRule() {
  return useMutation({
    mutationFn: (id: string) => api.post<RuleTestResult>(`/rules/${id}/test`),
  });
}
