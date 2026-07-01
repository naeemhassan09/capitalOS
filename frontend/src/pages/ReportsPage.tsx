import { useState } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { Download, FileBarChart } from 'lucide-react';
import {
  useMonthlyReport,
  useCategorySpendingReport,
  useNetWorthHistoryReport,
  useLiabilitiesReport,
  useGoalFundingReport,
  useAnnualSummaryReport,
} from '@/api/reports';
import { useDashboard } from '@/api/dashboard';
import { exportsApi } from '@/api/exports';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { formatMoney, formatMoneyCompact, formatPercent } from '@/utils/money';
import { formatDate } from '@/utils/date';
import { GOAL_STATUS_LABELS, COUNTRY_LABELS } from '@/utils/labels';
import { chartColors } from '@/components/charts';
import { PageHeader } from '@/components/PageHeader';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { Input } from '@/components/ui/Input';
import { Field } from '@/components/ui/Label';
import { Badge } from '@/components/ui/Badge';
import {
  Table,
  TableContainer,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  TableEmpty,
} from '@/components/ui/Table';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import type { Currency } from '@/types';

type ReportKey =
  | 'monthly'
  | 'category-spending'
  | 'net-worth-history'
  | 'liabilities'
  | 'goal-funding'
  | 'annual-summary';

const REPORTS: { value: ReportKey; label: string }[] = [
  { value: 'monthly', label: 'Monthly income & expenses' },
  { value: 'category-spending', label: 'Category spending' },
  { value: 'net-worth-history', label: 'Net-worth history' },
  { value: 'liabilities', label: 'Liabilities' },
  { value: 'goal-funding', label: 'Goal funding' },
  { value: 'annual-summary', label: 'Annual summary' },
];

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

// A small span of recent years for the year/month pickers.
function recentYears(count = 6): number[] {
  const now = new Date().getFullYear();
  return Array.from({ length: count }, (_, i) => now - i);
}

interface DateRange {
  date_from?: string;
  date_to?: string;
  [key: string]: string | undefined;
}

export function ReportsPage() {
  const [report, setReport] = useState<ReportKey>('monthly');
  const [range, setRange] = useState<DateRange>({});
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const dashboard = useDashboard();
  const base = dashboard.data?.base_currency ?? 'EUR';
  const colors = chartColors();
  const toast = useToast();

  const usesDateRange = report === 'category-spending' || report === 'net-worth-history';
  const usesMonthPicker = report === 'monthly';
  const usesYearPicker = report === 'annual-summary';
  const years = recentYears();

  const doExport = async (fn: () => Promise<void>, label: string) => {
    try {
      await fn();
    } catch (err) {
      toast.error(`Could not export ${label}`, err instanceof ApiError ? err.message : undefined);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Reports" description="Analyse trends and export your data." />

      <Card>
        <CardContent className="pt-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
            <Field label="Report" className="sm:col-span-2">
              <Select value={report} onChange={(e) => setReport(e.target.value as ReportKey)}>
                {REPORTS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </Select>
            </Field>

            {usesMonthPicker && (
              <>
                <Field label="Year">
                  <Select value={year} onChange={(e) => setYear(Number(e.target.value))}>
                    {years.map((y) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Month">
                  <Select value={month} onChange={(e) => setMonth(Number(e.target.value))}>
                    {MONTHS.map((m, i) => (
                      <option key={m} value={i + 1}>
                        {m}
                      </option>
                    ))}
                  </Select>
                </Field>
              </>
            )}

            {usesYearPicker && (
              <Field label="Year" className="sm:col-span-2">
                <Select value={year} onChange={(e) => setYear(Number(e.target.value))}>
                  {years.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </Select>
              </Field>
            )}

            {usesDateRange && (
              <>
                <Field label="From">
                  <Input
                    type="date"
                    value={range.date_from ?? ''}
                    onChange={(e) => setRange((r) => ({ ...r, date_from: e.target.value }))}
                  />
                </Field>
                <Field label="To">
                  <Input
                    type="date"
                    value={range.date_to ?? ''}
                    onChange={(e) => setRange((r) => ({ ...r, date_to: e.target.value }))}
                  />
                </Field>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="min-h-[200px]">
        {report === 'monthly' && <MonthlyReport year={year} month={month} base={base} colors={colors} />}
        {report === 'category-spending' && <CategoryReport range={range} base={base} colors={colors} />}
        {report === 'net-worth-history' && <NetWorthReport base={base} colors={colors} />}
        {report === 'liabilities' && <LiabilitiesReport base={base} />}
        {report === 'goal-funding' && <GoalFundingReport />}
        {report === 'annual-summary' && <AnnualReport year={year} base={base} colors={colors} />}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Export data</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => doExport(exportsApi.full, 'full backup')}>
              <Download className="h-4 w-4" /> Full backup (JSON)
            </Button>
            <Button variant="outline" size="sm" onClick={() => doExport(exportsApi.transactions, 'transactions')}>
              <Download className="h-4 w-4" /> Transactions CSV
            </Button>
            <Button variant="outline" size="sm" onClick={() => doExport(exportsApi.accounts, 'accounts')}>
              <Download className="h-4 w-4" /> Accounts CSV
            </Button>
            <Button variant="outline" size="sm" onClick={() => doExport(exportsApi.goals, 'goals')}>
              <Download className="h-4 w-4" /> Goals CSV
            </Button>
            <Button variant="outline" size="sm" onClick={() => doExport(exportsApi.holdings, 'holdings')}>
              <Download className="h-4 w-4" /> Holdings CSV
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

type ChartColors = ReturnType<typeof chartColors>;

function tooltipStyle(colors: ChartColors) {
  return {
    background: 'hsl(var(--popover))',
    border: `1px solid ${colors.grid}`,
    borderRadius: 8,
    fontSize: 12,
  } as const;
}

interface ReportQueryState {
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => unknown;
}

function ReportShell({
  title,
  query,
  empty,
  children,
}: {
  title: string;
  query: ReportQueryState;
  empty: boolean;
  children: React.ReactNode;
}) {
  const { isLoading, isError, error, refetch } = query;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : isError ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : empty ? (
          <div className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
            <FileBarChart className="h-8 w-8" />
            <p className="text-sm">No data for this period.</p>
          </div>
        ) : (
          children
        )}
      </CardContent>
    </Card>
  );
}

// Compact income/expenses/net/savings summary shared by the period reports.
function PeriodSummary({
  income,
  expenses,
  net,
  savingsRate,
  base,
}: {
  income: number;
  expenses: number;
  net: number;
  savingsRate: number;
  base: Currency;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <SummaryStat label="Income" value={formatMoney(income, base)} className="text-positive" />
      <SummaryStat label="Expenses" value={formatMoney(expenses, base)} className="text-negative" />
      <SummaryStat label="Net" value={formatMoney(net, base)} />
      <SummaryStat label="Savings rate" value={formatPercent(savingsRate)} />
    </div>
  );
}

function SummaryStat({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`mt-1 text-lg font-semibold tabular-nums ${className ?? 'text-foreground'}`}>{value}</p>
    </div>
  );
}

function MonthlyReport({
  year,
  month,
  base,
  colors,
}: {
  year: number;
  month: number;
  base: Currency;
  colors: ChartColors;
}) {
  const q = useMonthlyReport({ year, month });
  const data = q.data;
  const categories = data?.by_category ?? [];
  return (
    <ReportShell title="Monthly income & expenses" query={q} empty={!data || categories.length === 0}>
      {data && (
        <div className="space-y-4">
          <PeriodSummary
            income={data.income_base}
            expenses={data.expenses_base}
            net={data.net_base}
            savingsRate={data.savings_rate}
            base={base}
          />
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categories} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
                <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" />
                <XAxis dataKey="category" stroke={colors.muted} fontSize={12} interval={0} angle={-20} textAnchor="end" height={60} />
                <YAxis stroke={colors.muted} fontSize={12} tickFormatter={(v) => formatMoneyCompact(v, base)} width={70} />
                <Tooltip contentStyle={tooltipStyle(colors)} formatter={(v: number) => [formatMoney(v, base), 'Spend']} cursor={{ fill: colors.grid, opacity: 0.3 }} />
                <Bar dataKey="amount_base" name="Spend" fill={colors.negative} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <TableContainer>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Category</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {categories.map((c) => (
                  <TableRow key={c.category}>
                    <TableCell>{c.category}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatMoney(c.amount_base, base)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </div>
      )}
    </ReportShell>
  );
}

function CategoryReport({ range, base, colors }: { range: DateRange; base: Currency; colors: ChartColors }) {
  const q = useCategorySpendingReport(range);
  const data = q.data;
  const rows = (data?.by_category ?? []).slice().sort((a, b) => b.amount_base - a.amount_base);
  const total = data?.total_base ?? 0;
  return (
    <ReportShell title="Category spending" query={q} empty={rows.length === 0}>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows.slice(0, 12)} layout="vertical" margin={{ left: 12, right: 16 }}>
            <CartesianGrid horizontal={false} stroke={colors.grid} />
            <XAxis type="number" tickFormatter={(v) => formatMoneyCompact(v, base)} stroke={colors.muted} fontSize={12} />
            <YAxis type="category" dataKey="category" width={130} stroke={colors.muted} fontSize={12} />
            <Tooltip contentStyle={tooltipStyle(colors)} formatter={(v: number) => [formatMoney(v, base), 'Spend']} cursor={{ fill: colors.grid, opacity: 0.3 }} />
            <Bar dataKey="amount_base" fill={colors.negative} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <TableContainer className="mt-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Category</TableHead>
              <TableHead className="text-right">Amount</TableHead>
              <TableHead className="text-right">Share</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.category}>
                <TableCell>{r.category}</TableCell>
                <TableCell className="text-right tabular-nums">{formatMoney(r.amount_base, base)}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {total > 0 ? formatPercent(r.amount_base / total) : '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </ReportShell>
  );
}

function NetWorthReport({ base, colors }: { base: Currency; colors: ChartColors }) {
  const q = useNetWorthHistoryReport({ months: 12 });
  const data = q.data;
  const points = data?.points ?? [];
  return (
    <ReportShell title="Net-worth history" query={q} empty={points.length === 0}>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
            <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" />
            <XAxis dataKey="month_end" tickFormatter={(v) => formatDate(v, 'MMM yy')} stroke={colors.muted} fontSize={12} minTickGap={24} />
            <YAxis stroke={colors.muted} fontSize={12} tickFormatter={(v) => formatMoneyCompact(v, base)} width={70} />
            <Tooltip contentStyle={tooltipStyle(colors)} labelFormatter={(v) => formatDate(v)} formatter={(v: number, n) => [formatMoney(v, base), n as string]} />
            <Legend />
            <Line type="monotone" dataKey="total_net_worth_base" name="Net worth" stroke={colors.primary} strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="liquid_net_worth_base" name="Liquid" stroke={colors.positive} strokeWidth={1.5} dot={false} />
            <Line type="monotone" dataKey="liabilities_base" name="Liabilities" stroke={colors.negative} strokeWidth={1.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {data?.note && <p className="mt-3 text-xs text-muted-foreground">{data.note}</p>}
    </ReportShell>
  );
}

function LiabilitiesReport({ base }: { base: Currency }) {
  const q = useLiabilitiesReport({});
  const rows = q.data?.liabilities ?? [];
  return (
    <ReportShell title="Liabilities" query={q} empty={rows.length === 0}>
      <TableContainer>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Account</TableHead>
              <TableHead>Country</TableHead>
              <TableHead className="text-right">Balance</TableHead>
              <TableHead className="text-right">Credit limit</TableHead>
              <TableHead className="text-right">Utilisation</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableEmpty colSpan={5}>No liabilities.</TableEmpty>
            ) : (
              rows.map((r) => (
                <TableRow key={r.account_id}>
                  <TableCell>{r.name}</TableCell>
                  <TableCell>{COUNTRY_LABELS[r.country]}</TableCell>
                  <TableCell className="text-right tabular-nums text-negative">{formatMoney(r.balance_base, base)}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {r.credit_limit != null ? formatMoney(r.credit_limit, base) : '—'}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {r.utilisation != null ? formatPercent(r.utilisation) : '—'}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </ReportShell>
  );
}

function GoalFundingReport() {
  const q = useGoalFundingReport({});
  const rows = q.data?.goals ?? [];
  return (
    <ReportShell title="Goal funding" query={q} empty={rows.length === 0}>
      <TableContainer>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Goal</TableHead>
              <TableHead className="text-right">Target</TableHead>
              <TableHead className="text-right">Current</TableHead>
              <TableHead className="text-right">Funded</TableHead>
              <TableHead className="text-right">Req / month</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id}>
                <TableCell>{r.name}</TableCell>
                <TableCell className="text-right tabular-nums">{formatMoney(r.target_amount, r.currency)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatMoney(r.current_amount, r.currency)}</TableCell>
                <TableCell className="text-right tabular-nums">{`${Math.round(r.percent_funded)}%`}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {r.required_monthly_contribution != null
                    ? formatMoney(r.required_monthly_contribution, r.currency)
                    : '—'}
                </TableCell>
                <TableCell>
                  <Badge variant={r.status === 'on_track' || r.status === 'achieved' ? 'success' : 'warning'}>
                    {GOAL_STATUS_LABELS[r.status]}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </ReportShell>
  );
}

function AnnualReport({ year, base, colors }: { year: number; base: Currency; colors: ChartColors }) {
  const q = useAnnualSummaryReport({ year });
  const data = q.data;
  const categories = data?.by_category ?? [];
  return (
    <ReportShell title="Annual summary" query={q} empty={!data || categories.length === 0}>
      {data && (
        <div className="space-y-4">
          <PeriodSummary
            income={data.income_base}
            expenses={data.expenses_base}
            net={data.net_base}
            savingsRate={data.savings_rate}
            base={base}
          />
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categories} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
                <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" />
                <XAxis dataKey="category" stroke={colors.muted} fontSize={12} interval={0} angle={-20} textAnchor="end" height={60} />
                <YAxis stroke={colors.muted} fontSize={12} tickFormatter={(v) => formatMoneyCompact(v, base)} width={70} />
                <Tooltip contentStyle={tooltipStyle(colors)} formatter={(v: number) => [formatMoney(v, base), 'Spend']} cursor={{ fill: colors.grid, opacity: 0.3 }} />
                <Bar dataKey="amount_base" name="Spend" fill={colors.negative} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <TableContainer>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Category</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {categories.map((c) => (
                  <TableRow key={c.category}>
                    <TableCell>{c.category}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatMoney(c.amount_base, base)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </div>
      )}
    </ReportShell>
  );
}
