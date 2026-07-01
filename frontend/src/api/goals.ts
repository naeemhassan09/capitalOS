import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type { Goal, GoalWithProgress } from '@/types';

export type GoalInput = Omit<Goal, 'id'>;

export function useGoals() {
  return useQuery({
    queryKey: qk.goals,
    queryFn: () => api.get<GoalWithProgress[]>('/goals'),
  });
}

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: qk.goals });
  qc.invalidateQueries({ queryKey: qk.dashboard.summary });
}

export function useCreateGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<GoalInput>) => api.post<GoalWithProgress>('/goals', { json: payload }),
    onSuccess: () => invalidate(qc),
  });
}

export function useUpdateGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Partial<GoalInput> & { id: string }) =>
      api.patch<GoalWithProgress>(`/goals/${id}`, { json: payload }),
    onSuccess: () => invalidate(qc),
  });
}

export function useDeleteGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/goals/${id}`),
    onSuccess: () => invalidate(qc),
  });
}
