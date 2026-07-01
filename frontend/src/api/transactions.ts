import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type {
  Transaction,
  TransactionCreate,
  TransactionQuery,
  Paginated,
  TransferCandidate,
} from '@/types';

export function useTransactions(query: TransactionQuery) {
  return useQuery({
    queryKey: qk.transactions.list(query),
    queryFn: () =>
      api.get<Paginated<Transaction>>('/transactions', {
        params: query as Record<string, string | number | boolean | undefined>,
      }),
    placeholderData: (prev) => prev, // keep previous page while paginating
  });
}

export function useTransaction(id: string | undefined) {
  return useQuery({
    queryKey: qk.transactions.detail(id ?? ''),
    queryFn: () => api.get<Transaction>(`/transactions/${id}`),
    enabled: !!id,
  });
}

function invalidateTx(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['transactions'] });
  qc.invalidateQueries({ queryKey: qk.dashboard.summary });
  qc.invalidateQueries({ queryKey: qk.accounts.all });
}

export function useCreateTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: TransactionCreate) => api.post<Transaction>('/transactions', { json: payload }),
    onSuccess: () => invalidateTx(qc),
  });
}

export interface TransferCreate {
  from_account_id: string;
  to_account_id: string;
  amount: string | number;
  booking_date: string;
  description?: string | null;
  category_id?: string | null;
}

export function useCreateTransfer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: TransferCreate) =>
      api.post<{ group_id: string }>('/transactions/transfer', { json: payload }),
    onSuccess: () => invalidateTx(qc),
  });
}

export function useUpdateTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Partial<TransactionCreate> & { id: string }) =>
      api.patch<Transaction>(`/transactions/${id}`, { json: payload }),
    onSuccess: () => invalidateTx(qc),
  });
}

export function useDeleteTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/transactions/${id}`),
    onSuccess: () => invalidateTx(qc),
  });
}

export function useBulkCategorise() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { ids: string[]; category_id: string | null; mark_reviewed?: boolean }) =>
      api.post<{ updated: number }>('/transactions/bulk-categorise', { json: payload }),
    onSuccess: () => invalidateTx(qc),
  });
}

export function useBulkReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { ids: string[]; is_reviewed: boolean }) =>
      api.post<{ updated: number }>('/transactions/bulk-review', { json: payload }),
    onSuccess: () => invalidateTx(qc),
  });
}

export function useTransferCandidates(days: number, tolerance: number, enabled = true) {
  return useQuery({
    queryKey: qk.transactions.transferCandidates(days, tolerance),
    queryFn: () =>
      api.get<TransferCandidate[]>('/transactions/transfer-candidates', {
        params: { days, tolerance },
      }),
    enabled,
  });
}

export function useLinkTransfer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { debit_id: string; credit_id: string }) =>
      api.post<{ transfer_group_id: string }>('/transactions/transfers', { json: payload }),
    onSuccess: () => {
      invalidateTx(qc);
      qc.invalidateQueries({ queryKey: ['transactions', 'transfer-candidates'] });
    },
  });
}

export function useUnlinkTransfer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (groupId: string) => api.delete<void>(`/transactions/transfers/${groupId}`),
    onSuccess: () => invalidateTx(qc),
  });
}
