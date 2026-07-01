import type {
  AccountType,
  Country,
  TxKind,
  TxStatus,
  TxDirection,
  AssetClass,
  LiquidityClass,
  GoalStatus,
} from '@/types';

export const COUNTRY_LABELS: Record<Country, string> = {
  IE: 'Ireland',
  PK: 'Pakistan',
  OTHER: 'Other',
};

export const COUNTRY_FLAGS: Record<Country, string> = {
  IE: '\u{1F1EE}\u{1F1EA}',
  PK: '\u{1F1F5}\u{1F1F0}',
  OTHER: '\u{1F30D}',
};

export const ACCOUNT_TYPE_LABELS: Record<AccountType, string> = {
  current: 'Current',
  savings: 'Savings',
  credit_card: 'Credit card',
  cash: 'Cash',
  investment: 'Investment',
  pension: 'Pension',
  property: 'Property',
  loan: 'Loan',
  receivable: 'Receivable',
  other_asset: 'Other asset',
  other_liability: 'Other liability',
};

export const LIABILITY_TYPES = new Set<AccountType>([
  'credit_card',
  'loan',
  'other_liability',
]);

export const TX_KIND_LABELS: Record<TxKind, string> = {
  expense: 'Expense',
  income: 'Income',
  transfer: 'Transfer',
  adjustment: 'Adjustment',
  fee: 'Fee',
  refund: 'Refund',
  other: 'Other',
};

export const TX_STATUS_LABELS: Record<TxStatus, string> = {
  settled: 'Settled',
  pending: 'Pending',
  projected: 'Projected',
};

export const TX_DIRECTION_LABELS: Record<TxDirection, string> = {
  credit: 'Credit (in)',
  debit: 'Debit (out)',
};

export const ASSET_CLASS_LABELS: Record<AssetClass, string> = {
  cash: 'Cash',
  stock: 'Stock',
  etf: 'ETF',
  mutual_fund: 'Mutual fund',
  pension: 'Pension',
  crypto: 'Crypto',
  commodity: 'Commodity',
  property: 'Property',
  private_equity: 'Private equity',
  other: 'Other',
};

export const LIQUIDITY_LABELS: Record<LiquidityClass, string> = {
  immediate: 'Immediate (deployable)',
  short_term: 'Short-term',
  restricted: 'Restricted',
  illiquid: 'Illiquid',
};

export const GOAL_STATUS_LABELS: Record<GoalStatus, string> = {
  on_track: 'On track',
  at_risk: 'At risk',
  behind: 'Behind',
  achieved: 'Achieved',
  paused: 'Paused',
};
