/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, type ReactNode } from 'react';
import type { User } from '@/types';

interface AuthContextValue {
  user: User;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ user, children }: { user: User; children: ReactNode }) {
  return <AuthContext.Provider value={{ user }}>{children}</AuthContext.Provider>;
}

/** Access the authenticated user. Only valid inside the guarded app tree. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
