import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type { Account, AccountCreate, BalanceAdjustment } from '@/types';

// Editable fields plus archive toggle.
export type AccountUpdate = Partial<AccountCreate> & { is_archived?: boolean };

export function useAccounts() {
  return useQuery({
    queryKey: qk.accounts.all,
    queryFn: () => api.get<Account[]>('/accounts'),
  });
}

export function useAccount(id: string | undefined) {
  return useQuery({
    queryKey: qk.accounts.detail(id ?? ''),
    queryFn: () => api.get<Account>(`/accounts/${id}`),
    enabled: !!id,
  });
}

function invalidateAccounts(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: qk.accounts.all });
  qc.invalidateQueries({ queryKey: qk.dashboard.summary });
}

export function useCreateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: AccountCreate) => api.post<Account>('/accounts', { json: payload }),
    onSuccess: () => invalidateAccounts(qc),
  });
}

export function useUpdateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: AccountUpdate & { id: string }) =>
      api.patch<Account>(`/accounts/${id}`, { json: payload }),
    onSuccess: () => invalidateAccounts(qc),
  });
}

export function useDeleteAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/accounts/${id}`),
    onSuccess: () => invalidateAccounts(qc),
  });
}

export function useAdjustBalance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: BalanceAdjustment & { id: string }) =>
      api.post<Account>(`/accounts/${id}/adjust-balance`, { json: payload }),
    onSuccess: () => {
      invalidateAccounts(qc);
      qc.invalidateQueries({ queryKey: ['transactions'] });
    },
  });
}
