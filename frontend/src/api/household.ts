import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type { HouseholdMember } from '@/types';

export type HouseholdInput = Omit<HouseholdMember, 'id'>;

export function useHousehold() {
  return useQuery({
    queryKey: qk.household,
    queryFn: () => api.get<HouseholdMember[]>('/household'),
  });
}

export function useCreateHouseholdMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: HouseholdInput) => api.post<HouseholdMember>('/household', { json: payload }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.household }),
  });
}

export function useUpdateHouseholdMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Partial<HouseholdInput> & { id: string }) =>
      api.patch<HouseholdMember>(`/household/${id}`, { json: payload }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.household }),
  });
}

export function useDeleteHouseholdMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/household/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.household }),
  });
}
