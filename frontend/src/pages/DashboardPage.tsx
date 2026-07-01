import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  Banknote,
  Wallet,
  ShieldCheck,
  TrendingUp,
  TrendingDown,
  PiggyBank,
  Landmark,
  Coins,
  ArrowRight,
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from 'recharts';
import { useDashboard } from '@/api/dashboard';
import { useCategorySpendingReport } from '@/api/reports';
import { formatMoney, formatMoneyCompact, formatPercent } from '@/utils/money';
import { formatDate } from '@/utils/date';
import { COUNTRY_LABELS, COUNTRY_FLAGS } from '@/utils/labels';
import { categoricalPalette, chartColors } from '@/components/charts';
import { PageHeader } from '@/components/PageHeader';
import { MetricCard } from '@/components/MetricCard';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Progress } from '@/components/ui/Progress';
import { SkeletonCards, Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { EmptyState } from '@/components/ui/EmptyState';
import type { Currency, WarningLevel, DashboardGoal } from '@/types';

const WARNING_VARIANT: Record<WarningLevel, 'danger' | 'warning' | 'info'> = {
  danger: 'danger',
  warning: 'warning',
  info: 'info',
};

export function DashboardPage() {
  const { data, isLoading, isError, error, refetch } = useDashboard();
  const spending = useCategorySpendingReport({}, true);

  const base = data?.base_currency ?? 'EUR';

  const jurisdictionByCountry = useMemo(() => {
    const map: Record<string, number> = {};
    for (const j of data?.jurisdiction_cash ?? []) {
      map[j.country] = j.deployable_base;
    }
    return map;
  }, [data]);
  const ieCash = jurisdictionByCountry.IE ?? 0;
  const pkCash = jurisdictionByCountry.PK ?? 0;

  const deployableTotal = data?.deployable.total_base ?? 0;
  const deployableNegative = deployableTotal < 0;

  const currencyPie = useMemo(() => {
    const exposure = data?.currency_exposure;
    if (!exposure) return [];
    const total =
      Object.values(exposure).reduce((s, v) => s + Math.abs(Number(v)), 0) || 1;
    return Object.entries(exposure).map(([currency, amount]) => ({
      name: currency,
      value: Math.abs(Number(amount)),
      percent: (Math.abs(Number(amount)) / total) * 100,
    }));
  }, [data]);

  const spendingBars = useMemo(() => {
    const rows = spending.data?.by_category ?? [];
    return rows
      .filter((r) => r.amount_base > 0)
      .sort((a, b) => b.amount_base - a.amount_base)
      .slice(0, 8)
      .map((r) => ({ name: r.category, amount: r.amount_base }));
  }, [spending.data]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Dashboard" />
        <SkeletonCards count={4} />
        <SkeletonCards count={4} />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="space-y-6">
        <PageHeader title="Dashboard" />
        <ErrorState error={error} onRetry={() => refetch()} />
      </div>
    );
  }

  const palette = categoricalPalette();
  const colors = chartColors();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description={`Everything in ${base}. Settled figures reflect cleared balances; projected figures look 30 days ahead.`}
      />

      {/* Warnings */}
      {data.warnings.length > 0 && (
        <div className="space-y-2">
          {data.warnings.map((w, i) => (
            <Alert key={`${w.code}-${i}`} variant={WARNING_VARIANT[w.level]} title={w.message} />
          ))}
        </div>
      )}

      {/* TRUE DEPLOYABLE CAPITAL — prominent, red when negative */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <MetricCard
          className="lg:col-span-1"
          prominent
          tone={deployableNegative ? 'negative' : 'deployable'}
          label="True deployable capital"
          value={formatMoney(deployableTotal, base)}
          icon={<Coins className="h-5 w-5" />}
          sub={
            deployableNegative
              ? 'Below required reserves — do not treat as available'
              : 'Liquid assets net of liabilities, committed expenses & protected reserves'
          }
        />
        <MetricCard
          label="Settled net position"
          value={formatMoney(data.settled.net_base, base)}
          tone={data.settled.net_base < 0 ? 'negative' : 'positive'}
          icon={<Banknote className="h-5 w-5" />}
          sub={`Assets ${formatMoneyCompact(data.settled.assets_base, base)} · Liab. ${formatMoneyCompact(
            data.settled.liabilities_base,
            base,
          )}`}
        />
        <MetricCard
          label="Projected 30-day net"
          value={formatMoney(data.projected_30d.projected_net_base, base)}
          tone={data.projected_30d.delta_base < 0 ? 'negative' : 'positive'}
          icon={data.projected_30d.delta_base < 0 ? <TrendingDown className="h-5 w-5" /> : <TrendingUp className="h-5 w-5" />}
          delta={{
            value: formatMoney(Math.abs(data.projected_30d.delta_base), base, { showSymbol: true }),
            positive: data.projected_30d.delta_base >= 0,
          }}
          sub="vs. today"
        />
      </div>

      {/* Jurisdiction cash + core liquidity metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label={`${COUNTRY_FLAGS.IE} Ireland cash`}
          value={formatMoney(ieCash, base)}
          icon={<Landmark className="h-5 w-5" />}
        />
        <MetricCard
          label={`${COUNTRY_FLAGS.PK} Pakistan cash`}
          value={formatMoney(pkCash, base)}
          icon={<Landmark className="h-5 w-5" />}
        />
        <MetricCard
          label="Liquid assets"
          value={formatMoney(data.liquid_assets_base, base)}
          tone="positive"
          icon={<Wallet className="h-5 w-5" />}
        />
        <MetricCard
          label="Protected reserves"
          value={formatMoney(data.protected_reserves_base, base)}
          tone="protected"
          icon={<ShieldCheck className="h-5 w-5" />}
        />
      </div>

      {/* Income / expense / liabilities / savings */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Current liabilities"
          value={formatMoney(data.current_liabilities_base, base)}
          tone="negative"
          icon={<TrendingDown className="h-5 w-5" />}
        />
        <MetricCard
          label="Monthly income"
          value={formatMoney(data.monthly_income_base, base)}
          tone="positive"
          icon={<TrendingUp className="h-5 w-5" />}
        />
        <MetricCard
          label="Monthly expenses"
          value={formatMoney(data.monthly_expenses_base, base)}
          tone="negative"
          icon={<TrendingDown className="h-5 w-5" />}
          sub={`3m avg ${formatMoneyCompact(data.rolling_3m_avg_spend_base, base)}`}
        />
        <MetricCard
          label="Savings rate"
          value={formatPercent(data.savings_rate)}
          tone={data.savings_rate < 0 ? 'negative' : 'positive'}
          icon={<PiggyBank className="h-5 w-5" />}
        />
      </div>

      {/* Deployable capital by jurisdiction */}
      <Card>
        <CardHeader>
          <CardTitle>Deployable capital by jurisdiction</CardTitle>
        </CardHeader>
        <CardContent>
          {data.deployable.by_jurisdiction.length === 0 ? (
            <p className="text-sm text-muted-foreground">No jurisdiction data yet.</p>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
              {data.deployable.by_jurisdiction.map((j) => {
                const neg = j.deployable_base < 0;
                return (
                  <div key={j.country} className="rounded-lg border border-border p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-foreground">
                        {COUNTRY_FLAGS[j.country]} {COUNTRY_LABELS[j.country]}
                      </span>
                      <span
                        className={
                          neg ? 'text-sm font-semibold text-danger' : 'text-sm font-semibold text-deployable'
                        }
                      >
                        {formatMoney(j.deployable_base, base)}
                      </span>
                    </div>
                    <dl className="mt-2 space-y-1 text-xs text-muted-foreground">
                      <Row label="Liquid" value={formatMoney(j.liquid_base, base)} />
                      <Row label="Liabilities" value={formatMoney(-Math.abs(j.liabilities_base), base)} />
                      <Row
                        label="Committed"
                        value={formatMoney(-Math.abs(j.committed_expenses_base), base)}
                      />
                      <Row
                        label="Protected"
                        value={formatMoney(-Math.abs(j.protected_reserves_base), base)}
                      />
                    </dl>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Charts row */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Currency exposure</CardTitle>
          </CardHeader>
          <CardContent>
            {currencyPie.length === 0 ? (
              <EmptyState title="No currency exposure yet" className="border-0" />
            ) : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={currencyPie}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={55}
                      outerRadius={90}
                      paddingAngle={2}
                    >
                      {currencyPie.map((_, i) => (
                        <Cell key={i} fill={palette[i % palette.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number, name) => [formatMoney(value, base), name as Currency]}
                      contentStyle={tooltipStyle(colors)}
                    />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Top expense categories</CardTitle>
          </CardHeader>
          <CardContent>
            {spending.isLoading ? (
              <Skeleton className="h-64 w-full" />
            ) : spendingBars.length === 0 ? (
              <EmptyState title="No spending recorded yet" className="border-0" />
            ) : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={spendingBars} layout="vertical" margin={{ left: 12, right: 12 }}>
                    <CartesianGrid horizontal={false} stroke={colors.grid} />
                    <XAxis
                      type="number"
                      tickFormatter={(v) => formatMoneyCompact(v, base)}
                      stroke={colors.muted}
                      fontSize={12}
                    />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={110}
                      stroke={colors.muted}
                      fontSize={12}
                    />
                    <Tooltip
                      formatter={(value: number) => [formatMoney(value, base), 'Spend']}
                      contentStyle={tooltipStyle(colors)}
                      cursor={{ fill: colors.grid, opacity: 0.3 }}
                    />
                    <Bar dataKey="amount" fill={colors.negative} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Goals + upcoming obligations */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Goal progress</CardTitle>
            <Link to="/goals" className="text-sm text-primary hover:underline">
              View all
            </Link>
          </CardHeader>
          <CardContent className="space-y-4">
            {data.goals.length === 0 ? (
              <EmptyState title="No goals yet" className="border-0" />
            ) : (
              data.goals.slice(0, 4).map((g) => <GoalRow key={g.id} item={g} base={base} />)
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Upcoming obligations</CardTitle>
            <Link to="/cash-flow" className="text-sm text-primary hover:underline">
              Cash flow
            </Link>
          </CardHeader>
          <CardContent>
            {data.upcoming_obligations.length === 0 ? (
              <EmptyState title="Nothing due soon" className="border-0" />
            ) : (
              <ul className="divide-y divide-border">
                {data.upcoming_obligations.slice(0, 6).map((o, i) => (
                  <li key={`${o.name}-${i}`} className="flex items-center justify-between gap-3 py-2.5">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">{o.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(o.due_date)} · {COUNTRY_FLAGS[o.country]} {COUNTRY_LABELS[o.country]}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold tabular-nums text-foreground">
                        {formatMoney(o.base_amount, base)}
                      </p>
                      {o.currency !== base && (
                        <p className="text-xs text-muted-foreground">
                          {formatMoney(o.amount, o.currency)}
                        </p>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="flex justify-end">
        <Link
          to="/reports"
          className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
        >
          Explore detailed reports <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <dt>{label}</dt>
      <dd className="tabular-nums">{value}</dd>
    </div>
  );
}

function GoalRow({ item, base }: { item: DashboardGoal; base: Currency }) {
  const pct = Math.max(0, Math.min(100, Math.round(item.percent_funded)));
  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="truncate text-sm font-medium text-foreground">{item.name}</span>
        <Badge variant={item.on_track ? 'success' : 'warning'}>
          {item.on_track ? 'On track' : 'At risk'}
        </Badge>
      </div>
      <Progress
        value={pct}
        indicatorClassName={item.on_track ? 'bg-deployable' : 'bg-warning'}
      />
      <div className="mt-1 flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {formatMoney(item.current_amount, base)} / {formatMoney(item.target_amount, item.currency)}
        </span>
        <span>{pct}%</span>
      </div>
    </div>
  );
}

function tooltipStyle(colors: ReturnType<typeof chartColors>) {
  return {
    background: 'hsl(var(--popover))',
    border: `1px solid ${colors.grid}`,
    borderRadius: 8,
    color: 'hsl(var(--popover-foreground))',
    fontSize: 12,
  } as const;
}
