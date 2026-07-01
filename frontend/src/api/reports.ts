import { useQuery } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type {
  MonthlyReport,
  CategorySpending,
  NetWorthHistory,
  LiabilitiesReport,
  GoalFundingReport,
  AnnualSummary,
} from '@/types';

export interface ReportDateRange {
  date_from?: string;
  date_to?: string;
  [key: string]: string | undefined;
}

// Some report endpoints take numeric params (year/month/months) rather than a
// date range, so the helper accepts any string|number query params.
export type ReportParams = Record<string, string | number | undefined>;

function useReport<T>(name: string, path: string, params: ReportParams, enabled = true) {
  return useQuery({
    queryKey: qk.reports(name, params),
    queryFn: () => api.get<T>(path, { params }),
    enabled,
  });
}

export function useMonthlyReport(params: ReportParams, enabled = true) {
  return useReport<MonthlyReport>('monthly', '/reports/monthly', params, enabled);
}

export function useCategorySpendingReport(params: ReportParams, enabled = true) {
  return useReport<CategorySpending>(
    'category-spending',
    '/reports/category-spending',
    params,
    enabled,
  );
}

export function useNetWorthHistoryReport(params: ReportParams, enabled = true) {
  return useReport<NetWorthHistory>(
    'net-worth-history',
    '/reports/net-worth-history',
    params,
    enabled,
  );
}

export function useLiabilitiesReport(params: ReportParams, enabled = true) {
  return useReport<LiabilitiesReport>('liabilities', '/reports/liabilities', params, enabled);
}

export function useGoalFundingReport(params: ReportParams, enabled = true) {
  return useReport<GoalFundingReport>('goal-funding', '/reports/goal-funding', params, enabled);
}

export function useAnnualSummaryReport(params: ReportParams, enabled = true) {
  return useReport<AnnualSummary>('annual-summary', '/reports/annual-summary', params, enabled);
}
