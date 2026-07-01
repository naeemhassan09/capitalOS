import { api } from './client';

// Export endpoints trigger browser downloads via the shared download helper.
export const exportsApi = {
  full: () => api.download('/exports/full.json', 'capitalos-export.json'),
  transactions: () => api.download('/exports/transactions.csv', 'transactions.csv'),
  accounts: () => api.download('/exports/accounts.csv', 'accounts.csv'),
  goals: () => api.download('/exports/goals.csv', 'goals.csv'),
  holdings: () => api.download('/exports/holdings.csv', 'holdings.csv'),
};
