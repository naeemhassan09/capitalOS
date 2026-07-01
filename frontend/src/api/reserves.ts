import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type { Reserve } from '@/types';

export type ReserveInput = Omit<Reserve, 'id'>;

export function useReserves() {
  return useQuery({
    queryKey: qk.reserves,
    queryFn: () => api.get<Reserve[]>('/reserves'),
  });
}

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: qk.reserves });
  qc.invalidateQueries({ queryKey: qk.dashboard.summary });
}

export function useCreateReserve() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<ReserveInput>) => api.post<Reserve>('/reserves', { json: payload }),
    onSuccess: () => invalidate(qc),
  });
}

export function useUpdateReserve() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Partial<ReserveInput> & { id: string }) =>
      api.patch<Reserve>(`/reserves/${id}`, { json: payload }),
    onSuccess: () => invalidate(qc),
  });
}

export function useDeleteReserve() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/reserves/${id}`),
    onSuccess: () => invalidate(qc),
  });
}
