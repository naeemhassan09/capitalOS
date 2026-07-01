import type { TransactionQuery, CashflowScenario, CashflowHorizon } from '@/types';

// Centralised query-key factory so invalidation stays consistent.
export const qk = {
  auth: {
    setupStatus: ['auth', 'setup-status'] as const,
    me: ['auth', 'me'] as const,
    sessions: ['auth', 'sessions'] as const,
  },
  accounts: {
    all: ['accounts'] as const,
    detail: (id: string) => ['accounts', id] as const,
  },
  institutions: ['institutions'] as const,
  household: ['household'] as const,
  categories: ['categories'] as const,
  rules: ['rules'] as const,
  transactions: {
    list: (query: TransactionQuery) => ['transactions', 'list', query] as const,
    detail: (id: string) => ['transactions', id] as const,
    transferCandidates: (days: number, tolerance: number) =>
      ['transactions', 'transfer-candidates', days, tolerance] as const,
  },
  imports: {
    all: ['imports'] as const,
    importers: ['imports', 'importers'] as const,
    detail: (id: string) => ['imports', id] as const,
  },
  scheduledCashflows: ['scheduled-cashflows'] as const,
  budgets: {
    all: ['budgets'] as const,
    report: (year: number, month: number) => ['budgets', 'report', year, month] as const,
  },
  goals: ['goals'] as const,
  reserves: ['reserves'] as const,
  holdings: ['holdings'] as const,
  exchangeRates: ['exchange-rates'] as const,
  dashboard: {
    summary: ['dashboard'] as const,
    cashflow: (scenario: CashflowScenario, horizon: CashflowHorizon) =>
      ['dashboard', 'cashflow', scenario, horizon] as const,
  },
  reports: (name: string, params: Record<string, unknown>) => ['reports', name, params] as const,
};
