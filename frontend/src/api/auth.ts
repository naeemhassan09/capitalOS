import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type { User, SetupStatus, SessionInfo, Currency } from '@/types';

export interface SetupPayload {
  email: string;
  password: string;
  display_name: string;
  base_currency: Currency;
  timezone: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
}

export interface PinLoginPayload {
  pin: string;
}

export interface SetPinPayload {
  current_password: string;
  pin: string;
}

export function useSetupStatus() {
  return useQuery({
    queryKey: qk.auth.setupStatus,
    queryFn: () => api.get<SetupStatus>('/auth/setup-status'),
    staleTime: 60_000,
    retry: false,
  });
}

/** Current user; 401 is treated as "not logged in" (null), not an error. */
export function useMe() {
  return useQuery({
    queryKey: qk.auth.me,
    queryFn: async () => {
      try {
        return await api.get<User>('/auth/me');
      } catch (err) {
        if (typeof err === 'object' && err && 'status' in err && (err as { status: number }).status === 401) {
          return null;
        }
        throw err;
      }
    },
    retry: false,
    staleTime: 30_000,
  });
}

export function useSetup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SetupPayload) => api.post<User>('/auth/setup', { json: payload }),
    onSuccess: (user) => {
      qc.setQueryData(qk.auth.me, user);
      qc.setQueryData(qk.auth.setupStatus, { initialized: true, pin_enabled: false });
      qc.invalidateQueries();
    },
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: LoginPayload) => api.post<User>('/auth/login', { json: payload }),
    onSuccess: (user) => {
      qc.setQueryData(qk.auth.me, user);
      qc.invalidateQueries();
    },
  });
}

/** Sign in with a PIN. Public endpoint (no CSRF needed); refreshes the session queries like useLogin. */
export function usePinLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: PinLoginPayload) => api.post<User>('/auth/pin/login', { json: payload }),
    onSuccess: (user) => {
      qc.setQueryData(qk.auth.me, user);
      qc.invalidateQueries();
    },
  });
}

/** Set or change the account PIN (authenticated). */
export function useSetPin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SetPinPayload) => api.post<{ detail: string }>('/auth/pin', { json: payload }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.auth.setupStatus }),
  });
}

/** Remove the account PIN (authenticated). */
export function useRemovePin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<{ detail: string }>('/auth/pin'),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.auth.setupStatus }),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>('/auth/logout'),
    onSuccess: () => {
      qc.setQueryData(qk.auth.me, null);
      qc.clear();
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (payload: ChangePasswordPayload) =>
      api.post<void>('/auth/change-password', { json: payload }),
  });
}

export function useSessions() {
  return useQuery({
    queryKey: qk.auth.sessions,
    queryFn: () => api.get<SessionInfo[]>('/auth/sessions'),
  });
}

export function useRevokeSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/auth/sessions/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.auth.sessions }),
  });
}
