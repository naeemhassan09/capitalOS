import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type {
  Aspsp,
  BankConnection,
  BankLinkMapping,
  BankStatus,
  BankSyncResult,
  CompleteBankAuthResponse,
  DiscoveredBankAccount,
} from '@/types';

export function useBankStatus() {
  return useQuery({
    queryKey: qk.bankConnections.status,
    queryFn: () => api.get<BankStatus>('/bank-connections/status'),
  });
}

export function useBankConnections() {
  return useQuery({
    queryKey: qk.bankConnections.all,
    queryFn: () => api.get<BankConnection[]>('/bank-connections'),
  });
}

export function useAspsps(country: string, enabled: boolean) {
  return useQuery({
    queryKey: qk.bankConnections.aspsps(country),
    queryFn: () => api.get<Aspsp[]>('/bank-connections/aspsps', { params: { country } }),
    enabled,
    staleTime: 60 * 60 * 1000, // the bank list barely changes
  });
}

/** Re-discover the authorized bank accounts of an existing connection. */
export function useDiscoveredAccounts(connectionId: string | undefined) {
  return useQuery({
    queryKey: qk.bankConnections.discovered(connectionId ?? ''),
    queryFn: () =>
      api.get<DiscoveredBankAccount[]>(`/bank-connections/${connectionId}/accounts`),
    enabled: !!connectionId,
    retry: false,
  });
}

function invalidateConnections(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: qk.bankConnections.all });
}

function invalidateFinancials(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: qk.accounts.all });
  qc.invalidateQueries({ queryKey: ['transactions'] });
  qc.invalidateQueries({ queryKey: qk.dashboard.summary });
}

export function useConnectBank() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { aspsp_name: string; aspsp_country: string }) =>
      api.post<{ url: string; connection_id: string }>('/bank-connections/connect', {
        json: payload,
      }),
    onSuccess: () => invalidateConnections(qc),
  });
}

export function useCompleteBankAuth() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { code: string; state: string }) =>
      api.post<CompleteBankAuthResponse>('/bank-connections/complete', { json: payload }),
    onSuccess: () => {
      invalidateConnections(qc);
      invalidateFinancials(qc);
    },
  });
}

export function useCreateBankLinks() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { connection_id: string; mappings: BankLinkMapping[] }) =>
      api.post<BankConnection>('/bank-connections/links', { json: payload }),
    onSuccess: () => invalidateConnections(qc),
  });
}

export function useSyncBankConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<BankSyncResult>(`/bank-connections/${id}/sync`),
    onSuccess: () => {
      invalidateConnections(qc);
      invalidateFinancials(qc);
    },
  });
}

export function useDeleteBankConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<{ detail: string }>(`/bank-connections/${id}`),
    onSuccess: () => invalidateConnections(qc),
  });
}
