import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type { Institution } from '@/types';

export type InstitutionInput = Omit<Institution, 'id'>;

export function useInstitutions() {
  return useQuery({
    queryKey: qk.institutions,
    queryFn: () => api.get<Institution[]>('/institutions'),
  });
}

export function useCreateInstitution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: InstitutionInput) => api.post<Institution>('/institutions', { json: payload }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.institutions }),
  });
}

export function useUpdateInstitution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Partial<InstitutionInput> & { id: string }) =>
      api.patch<Institution>(`/institutions/${id}`, { json: payload }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.institutions }),
  });
}

export function useDeleteInstitution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/institutions/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.institutions }),
  });
}
