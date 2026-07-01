import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type { Category } from '@/types';

export interface CategoryInput {
  name: string;
  parent_id?: string | null;
  is_income?: boolean;
  is_essential?: boolean;
}

export function useCategories() {
  return useQuery({
    queryKey: qk.categories,
    queryFn: () => api.get<Category[]>('/categories'),
    staleTime: 60_000,
  });
}

/** Flatten the category tree into "Parent / Child" labelled entries. */
export function useFlatCategories() {
  const query = useCategories();
  const flat: { id: string; label: string; is_income: boolean }[] = [];
  const walk = (nodes: Category[] | undefined, prefix: string) => {
    for (const node of nodes ?? []) {
      const label = prefix ? `${prefix} / ${node.name}` : node.name;
      flat.push({ id: node.id, label, is_income: node.is_income });
      walk(node.children, label);
    }
  };
  walk(query.data, '');
  return { ...query, flat };
}

export function useCreateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CategoryInput) => api.post<Category>('/categories', { json: payload }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.categories }),
  });
}

export function useUpdateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Partial<CategoryInput> & { id: string }) =>
      api.patch<Category>(`/categories/${id}`, { json: payload }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.categories }),
  });
}

export function useDeleteCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/categories/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.categories }),
  });
}
