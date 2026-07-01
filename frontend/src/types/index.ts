// Domain types mirroring the CapitalOS FastAPI backend contract.

export type Currency = 'EUR' | 'PKR' | 'USD' | 'GBP' | 'SAR';
export type Country = 'IE' | 'PK' | 'OTHER';

export interface User {
  id: string;
  email: string;
  display_name: string;
  base_currency: Currency;
  timezone: string;
  is_owner: boolean;
  totp_enabled: boolean;
  last_login_at: string | null;
}

export interface SetupStatus {
  initialized: boolean;
  pin_enabled: boolean;
}

export interface SessionInfo {
  id: string;
  created_at: string;
  last_seen_at: string | null;
  user_agent: string | null;
  ip_address: string | null;
  is_current: boolean;
}

// --- Accounts ---
export type AccountType =
  | 'current'
  | 'savings'
  | 'credit_card'
  | 'cash'
  | 'investment'
  | 'pension'
  | 'property'
  | 'loan'
  | 'receivable'
  | 'other_asset'
  | 'other_liability';

export interface Account {
  id: string;
  name: string;
  account_type: AccountType;
  currency: Currency;
  country: Country;
  current_balance: number;
  credit_limit: number | null;
  include_in_net_worth: boolean;
  include_in_liquid_assets: boolean;
  is_protected_reserve: boolean;
  is_archived: boolean;
  institution_id: string | null;
  notes?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface AccountCreate {
  name: string;
  account_type: AccountType;
  currency: Currency;
  country: Country;
  current_balance?: number;
  credit_limit?: number | null;
  include_in_net_worth?: boolean;
  include_in_liquid_assets?: boolean;
  is_protected_reserve?: boolean;
  institution_id?: string | null;
  notes?: string | null;
}

export interface BalanceAdjustment {
  new_balance: number;
  note?: string;
  as_of?: string;
}

// --- Bank connections (Enable Banking) ---
export type BankConnectionStatus = 'pending' | 'active' | 'expired' | 'revoked';

export interface BankStatus {
  configured: boolean;
}

export interface Aspsp {
  name: string;
  country: string;
}

export interface BankAccountLink {
  id: string;
  account_id: string;
  display_name: string;
  identifier_masked: string | null;
  currency: string | null;
  enabled: boolean;
  last_synced_at: string | null;
}

export interface BankConnection {
  id: string;
  provider: string;
  aspsp_name: string;
  aspsp_country: string;
  status: BankConnectionStatus;
  valid_until: string | null;
  last_synced_at: string | null;
  created_at: string;
  links: BankAccountLink[];
}

export interface DiscoveredBankAccount {
  uid: string;
  name: string;
  identifier_masked: string;
  currency: string | null;
}

export interface CompleteBankAuthResponse {
  connection_id: string;
  aspsp_name: string;
  accounts: DiscoveredBankAccount[];
}

export interface BankLinkMapping {
  external_uid: string;
  account_id: string;
  display_name?: string;
  identifier_masked?: string | null;
  currency?: string | null;
}

export interface BankSyncResult {
  connection_id: string;
  accounts_synced: number;
  transactions_created: number;
  duplicates_skipped: number;
  errors: string[];
}

// --- Institutions ---
export type InstitutionType = 'bank' | 'broker' | 'pension' | 'wallet' | 'other';

export interface Institution {
  id: string;
  name: string;
  country: Country;
  institution_type: InstitutionType;
}

// --- Household ---
export type RelationshipType =
  | 'self'
  | 'spouse'
  | 'child'
  | 'parent'
  | 'sibling'
  | 'dependent'
  | 'other';

export interface HouseholdMember {
  id: string;
  name: string;
  relationship_type: RelationshipType;
  can_login: boolean;
}

// --- Categories ---
export interface Category {
  id: string;
  name: string;
  slug: string;
  parent_id: string | null;
  is_income: boolean;
  is_essential: boolean;
  is_system: boolean;
  children: Category[];
}

// --- Rules ---
export type RuleMatchField = 'description' | 'merchant' | 'amount' | 'account' | 'direction';
export type RuleOperator =
  | 'contains'
  | 'equals'
  | 'starts_with'
  | 'ends_with'
  | 'regex'
  | 'gt'
  | 'lt';

export interface Rule {
  id: string;
  name: string;
  priority: number;
  match_field: RuleMatchField;
  operator: RuleOperator;
  match_value: string;
  category_id: string | null;
  enabled: boolean;
  set_reviewed?: boolean;
  created_at?: string;
}

export interface RuleTestResult {
  matches: number;
}

// --- Transactions ---
export type TxDirection = 'credit' | 'debit';
export type TxKind = 'expense' | 'income' | 'transfer' | 'adjustment' | 'fee' | 'refund' | 'other';
export type TxStatus = 'settled' | 'pending' | 'projected';

export interface Transaction {
  id: string;
  account_id: string;
  booking_date: string;
  description: string;
  merchant: string | null;
  amount: number; // positive magnitude
  currency: Currency;
  direction: TxDirection;
  kind: TxKind;
  status: TxStatus;
  category_id: string | null;
  is_transfer: boolean;
  is_reviewed: boolean;
  transfer_group_id: string | null;
  notes: string | null;
}

export interface TransactionCreate {
  account_id: string;
  booking_date: string;
  description: string;
  merchant?: string | null;
  amount: number | string; // sent as a string for precision; backend accepts both
  currency: Currency;
  direction: TxDirection;
  kind?: TxKind;
  status?: TxStatus;
  category_id?: string | null;
  notes?: string | null;
}

export interface TransactionQuery {
  account_id?: string;
  category_id?: string;
  kind?: TxKind;
  status?: TxStatus;
  direction?: TxDirection;
  is_transfer?: boolean;
  is_reviewed?: boolean;
  search?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface TransferCandidate {
  debit: Transaction;
  credit: Transaction;
  confidence: number;
  fx_implied: number | null;
}

// --- Imports ---
export type ImportStatus =
  | 'uploaded'
  | 'previewed'
  | 'committed'
  | 'rolled_back'
  | 'failed';

export interface Importer {
  importer_type: string;
  display_name: string;
  needs_mapping: boolean;
}

export interface ImportBatch {
  id: string;
  account_id: string;
  importer_type: string;
  filename: string;
  status: ImportStatus;
  created_at: string;
  row_count?: number;
  imported_row_count?: number;
  duplicate_row_count?: number;
  rejected_row_count?: number;
}

export interface ImportPreviewRow {
  booking_date: string | null;
  description: string | null;
  merchant: string | null;
  amount: number | null;
  currency: string | null;
  direction: string | null;
  is_duplicate: boolean;
  suggested_category: string | null;
  error?: string | null;
  raw?: Record<string, string>;
}

export interface ImportPreview {
  rows: ImportPreviewRow[];
  total: number;
  duplicate_count: number;
  rejected: number;
  columns: string[];
}

// --- Scheduled cashflows ---
export type CashflowDirection = 'inflow' | 'outflow';
export type CashflowStatus = 'planned' | 'overdue' | 'paid' | 'skipped' | 'cancelled';

export interface ScheduledCashflow {
  id: string;
  name: string;
  direction: CashflowDirection;
  amount: number; // string over the wire — coerce with num()
  currency: Currency;
  first_due_date: string;
  next_due_date: string;
  recurrence_rule: string | null;
  status: CashflowStatus;
  priority: number;
  account_id?: string | null;
  category_id?: string | null;
}

// --- Budgets ---
export interface Budget {
  id: string;
  category_id: string;
  amount: number; // string over the wire — coerce with num()
  active: boolean;
}

export interface BudgetReportRow {
  id: string;
  category_id: string;
  category_name: string;
  amount: number; // monthly limit (base currency)
  actual_base: number; // spent this period
  remaining_base: number; // amount - actual (may be negative = over budget)
  percent_used: number; // 0..(>100)
  prev_month_base: number;
  avg_3m_base: number;
}

export interface BudgetReport {
  year: number;
  month: number;
  base_currency: Currency;
  total_budget_base: number;
  total_actual_base: number;
  rows: BudgetReportRow[];
}

// --- Goals ---
export type GoalStatus = 'on_track' | 'at_risk' | 'behind' | 'achieved' | 'paused';

export interface Goal {
  id: string;
  name: string;
  target_amount: number;
  currency: Currency;
  target_date: string | null;
  priority: number;
  current_amount?: number;
  linked_account_id?: string | null;
  notes?: string | null;
}

export interface GoalProgress {
  current_amount: number;
  percent_funded: number;
  remaining_amount: number;
  required_monthly_contribution: number;
  days_remaining: number | null;
  on_track: boolean;
  status: GoalStatus;
}

export interface GoalWithProgress {
  goal: Goal;
  progress: GoalProgress;
}

// Flat goal-progress shape returned inside the dashboard payload.
export interface DashboardGoal {
  id: string;
  name: string;
  currency: Currency;
  target_amount: number;
  current_amount: number;
  remaining_amount: number;
  percent_funded: number; // 0..100
  days_remaining: number | null;
  required_monthly_contribution: number | null;
  on_track: boolean;
  status: GoalStatus;
}

// --- Reserves ---
export interface Reserve {
  id: string;
  name: string;
  jurisdiction: Country;
  currency: Currency;
  target_amount: number;
  protected_amount: number;
  hard_floor: boolean;
}

// --- Holdings ---
// Must match the backend vocabulary (app/models/enums.py).
export type AssetClass =
  | 'cash'
  | 'stock'
  | 'etf'
  | 'mutual_fund'
  | 'pension'
  | 'crypto'
  | 'commodity'
  | 'property'
  | 'private_equity'
  | 'other';
export type LiquidityClass = 'immediate' | 'short_term' | 'restricted' | 'illiquid';

export interface Holding {
  id: string;
  asset_name: string;
  ticker: string | null;
  asset_class: AssetClass;
  quantity: number;
  native_currency: Currency;
  cost_basis: number;
  latest_valuation: number | null;
  valuation_date: string | null;
  liquidity_class: LiquidityClass;
  include_in_net_worth: boolean;
  valuation_is_manual: boolean;
}

export interface HoldingValuation {
  valuation_date: string;
  unit_price?: number;
  valuation: number;
}

// --- Exchange rates ---
export interface ExchangeRate {
  id: string;
  base_currency: Currency;
  quote_currency: Currency;
  rate: number;
  rate_date: string;
  source: string | null;
  is_manual: boolean;
}

export interface ConvertResult {
  amount: number;
  from: Currency;
  to: Currency;
  converted: number;
  rate: number;
  rate_date: string;
}

// --- Dashboard ---
export type WarningLevel = 'danger' | 'warning' | 'info';

export interface DashboardWarning {
  level: WarningLevel;
  code: string;
  message: string;
}

export interface SettledPosition {
  assets_base: number;
  liabilities_base: number;
  net_base: number;
}

export interface JurisdictionDeployable {
  country: Country;
  liquid_base: number;
  liabilities_base: number;
  committed_expenses_base: number;
  protected_reserves_base: number;
  deployable_base: number;
}

export interface DeployableCapital {
  total_base: number;
  by_jurisdiction: JurisdictionDeployable[];
}

export interface Projected30d {
  projected_net_base: number;
  delta_base: number;
  [key: string]: number;
}

export interface UpcomingObligation {
  name: string;
  due_date: string;
  amount: number;
  currency: Currency;
  base_amount: number;
  country: Country;
}

export interface JurisdictionCash {
  country: Country;
  deployable_base: number;
  projected_30d_net_base: number;
  hard_floor_base: number;
}

export interface NetWorthSummary {
  total_base: number;
  assets_base: number;
  liabilities_base: number;
  invested_base?: number;
  illiquid_base?: number;
  [key: string]: number | undefined;
}

export interface Dashboard {
  base_currency: Currency;
  settled: SettledPosition;
  settled_by_currency: Record<string, number>;
  liquid_assets_base: number;
  protected_reserves_base: number;
  current_liabilities_base: number;
  deployable: DeployableCapital;
  projected_30d: Projected30d;
  jurisdiction_cash: JurisdictionCash[];
  monthly_income_base: number;
  monthly_expenses_base: number;
  savings_rate: number;
  rolling_3m_avg_spend_base: number;
  rolling_6m_avg_spend_base: number;
  goals: DashboardGoal[];
  net_worth: NetWorthSummary;
  currency_exposure: Record<string, number>;
  upcoming_obligations: UpcomingObligation[];
  warnings: DashboardWarning[];
}

export type CashflowScenario = 'base' | 'conservative' | 'optimistic';
export type CashflowHorizon = 7 | 30 | 60 | 90;

export interface CashflowPoint {
  day: string;
  balance_base: number;
  inflow_base: number;
  outflow_base: number;
}

export interface CashflowProjection {
  points: CashflowPoint[];
  minimum_balance_base: number;
  minimum_balance_day: string;
  reserve_floor_base?: number;
  obligations: UpcomingObligation[];
}

// --- Reports ---
// Shapes mirror the backend `*Out` schemas in app/schemas/reports.py.
export interface CategoryAmount {
  category: string;
  amount_base: number;
}

export interface MonthlyReport {
  year: number;
  month: number;
  period_start: string;
  period_end: string;
  base_currency: Currency;
  income_base: number;
  expenses_base: number;
  net_base: number;
  savings_rate: number; // 0..1 fraction
  by_category: CategoryAmount[];
  warnings: string[];
}

export interface CategorySpending {
  date_from: string;
  date_to: string;
  base_currency: Currency;
  total_base: number;
  by_category: CategoryAmount[];
  warnings: string[];
}

export interface NetWorthPoint {
  month_end: string;
  total_net_worth_base: number;
  liquid_net_worth_base: number;
  liabilities_base: number;
  approximated: boolean;
}

export interface NetWorthHistory {
  base_currency: Currency;
  months: number;
  note: string;
  points: NetWorthPoint[];
  warnings: string[];
}

export interface LiabilityLine {
  account_id: string;
  name: string;
  account_type: AccountType;
  currency: Currency;
  country: Country;
  balance: number;
  balance_base: number;
  credit_limit: number | null;
  utilisation: number | null; // 0..1 fraction
}

export interface LiabilitiesReport {
  base_currency: Currency;
  total_liabilities_base: number;
  liabilities: LiabilityLine[];
  warnings: string[];
}

export interface GoalFunding {
  id: string;
  name: string;
  currency: Currency;
  target_amount: number;
  current_amount: number;
  remaining_amount: number;
  percent_funded: number; // 0..100 scale
  days_remaining: number | null;
  required_monthly_contribution: number | null;
  on_track: boolean;
  status: GoalStatus;
}

export interface GoalFundingReport {
  goals: GoalFunding[];
}

export interface AnnualSummary {
  year: number;
  period_start: string;
  period_end: string;
  base_currency: Currency;
  income_base: number;
  expenses_base: number;
  net_base: number;
  savings_rate: number; // 0..1 fraction
  by_category: CategoryAmount[];
  warnings: string[];
}
