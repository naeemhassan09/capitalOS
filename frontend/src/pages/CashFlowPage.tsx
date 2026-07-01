import { useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Area,
  ComposedChart,
} from 'recharts';
import { CalendarClock, TrendingDown } from 'lucide-react';
import { useCashflowProjection, useDashboard } from '@/api/dashboard';
import { formatMoney, formatMoneyCompact } from '@/utils/money';
import { formatDate, formatDateShort } from '@/utils/date';
import { COUNTRY_FLAGS, COUNTRY_LABELS } from '@/utils/labels';
import { chartColors } from '@/components/charts';
import { PageHeader } from '@/components/PageHeader';
import { SegmentedControl } from '@/components/ui/Tabs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { MetricCard } from '@/components/MetricCard';
import { Alert } from '@/components/ui/Alert';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { EmptyState } from '@/components/ui/EmptyState';
import type { CashflowScenario, CashflowHorizon } from '@/types';

const SCENARIOS: { value: CashflowScenario; label: string }[] = [
  { value: 'conservative', label: 'Conservative' },
  { value: 'base', label: 'Base' },
  { value: 'optimistic', label: 'Optimistic' },
];

const HORIZONS: { value: CashflowHorizon; label: string }[] = [
  { value: 7, label: '7d' },
  { value: 30, label: '30d' },
  { value: 60, label: '60d' },
  { value: 90, label: '90d' },
];

export function CashFlowPage() {
  const [scenario, setScenario] = useState<CashflowScenario>('base');
  const [horizon, setHorizon] = useState<CashflowHorizon>(30);

  const dashboard = useDashboard();
  const base = dashboard.data?.base_currency ?? 'EUR';
  const { data, isLoading, isError, error, refetch, isFetching } = useCashflowProjection(scenario, horizon);

  const colors = chartColors();

  const chartData = useMemo(() => {
    return (data?.points ?? []).map((p) => ({
      day: p.day,
      label: formatDateShort(p.day),
      balance: p.balance_base,
      inflow: p.inflow_base,
      outflow: -Math.abs(p.outflow_base),
    }));
  }, [data]);

  const floor = data?.reserve_floor_base ?? 0;
  const minBelowZero = (data?.minimum_balance_base ?? 0) < 0;
  const minBelowFloor = (data?.minimum_balance_base ?? 0) < floor;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cash flow"
        description="Projected daily balance across scenarios. The dashed line marks your reserve floor; zero is highlighted."
      />

      <div className="flex flex-wrap items-center gap-4">
        <SegmentedControl
          ariaLabel="Scenario"
          options={SCENARIOS}
          value={scenario}
          onChange={setScenario}
        />
        <SegmentedControl
          ariaLabel="Horizon"
          options={HORIZONS}
          value={horizon}
          onChange={setHorizon}
        />
        {isFetching && <span className="text-xs text-muted-foreground">Updating…</span>}
      </div>

      {isLoading ? (
        <Skeleton className="h-80 w-full" />
      ) : isError || !data ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <MetricCard
              label="Minimum balance"
              value={formatMoney(data.minimum_balance_base, base)}
              tone={minBelowZero ? 'negative' : minBelowFloor ? 'default' : 'positive'}
              prominent={minBelowZero}
              icon={<TrendingDown className="h-5 w-5" />}
              sub={`on ${formatDate(data.minimum_balance_day)}`}
            />
            <MetricCard
              label="Reserve floor"
              value={formatMoney(floor, base)}
              tone="protected"
              sub="Balance should stay above this"
            />
            <MetricCard
              label="Obligations in window"
              value={data.obligations.length}
              icon={<CalendarClock className="h-5 w-5" />}
            />
          </div>

          {minBelowZero && (
            <Alert variant="danger" title="Projected balance goes negative">
              Under the {scenario} scenario your balance falls below zero on{' '}
              {formatDate(data.minimum_balance_day)}. Consider deferring outflows or moving funds.
            </Alert>
          )}
          {!minBelowZero && minBelowFloor && (
            <Alert variant="warning" title="Projected balance dips below your reserve floor">
              Your buffer is breached during this window under the {scenario} scenario.
            </Alert>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Projected daily balance ({scenario})</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
                    <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="label" stroke={colors.muted} fontSize={12} minTickGap={24} />
                    <YAxis
                      stroke={colors.muted}
                      fontSize={12}
                      tickFormatter={(v) => formatMoneyCompact(v, base)}
                      width={70}
                    />
                    <Tooltip
                      formatter={(v: number) => [formatMoney(v, base), 'Balance']}
                      labelFormatter={(_, payload) => formatDate(payload?.[0]?.payload?.day)}
                      contentStyle={tooltipStyle(colors)}
                    />
                    <ReferenceLine y={0} stroke={colors.negative} strokeWidth={1.5} />
                    {floor !== 0 && (
                      <ReferenceLine
                        y={floor}
                        stroke={colors.protected}
                        strokeDasharray="6 4"
                        label={{ value: 'Reserve floor', position: 'insideTopLeft', fill: colors.protected, fontSize: 11 }}
                      />
                    )}
                    <Line
                      type="monotone"
                      dataKey="balance"
                      stroke={colors.primary}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Daily inflow vs outflow</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
                    <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="label" stroke={colors.muted} fontSize={12} minTickGap={24} />
                    <YAxis stroke={colors.muted} fontSize={12} tickFormatter={(v) => formatMoneyCompact(v, base)} width={70} />
                    <Tooltip contentStyle={tooltipStyle(colors)} formatter={(v: number, n) => [formatMoney(v, base), n as string]} />
                    <ReferenceLine y={0} stroke={colors.grid} />
                    <Area type="step" dataKey="inflow" stroke={colors.positive} fill={colors.positive} fillOpacity={0.25} name="Inflow" />
                    <Area type="step" dataKey="outflow" stroke={colors.negative} fill={colors.negative} fillOpacity={0.25} name="Outflow" />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Upcoming obligations</CardTitle>
            </CardHeader>
            <CardContent>
              {data.obligations.length === 0 ? (
                <EmptyState title="No obligations in this window" className="border-0" />
              ) : (
                <ul className="divide-y divide-border">
                  {data.obligations.map((o, i) => (
                    <li key={`${o.name}-${i}`} className="flex items-center justify-between gap-3 py-2.5">
                      <div className="flex min-w-0 items-center gap-3">
                        <div className="flex h-10 w-10 shrink-0 flex-col items-center justify-center rounded-md bg-muted text-center">
                          <span className="text-[10px] uppercase text-muted-foreground">
                            {formatDate(o.due_date, 'MMM')}
                          </span>
                          <span className="text-sm font-semibold leading-none text-foreground">
                            {formatDate(o.due_date, 'd')}
                          </span>
                        </div>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-foreground">{o.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {COUNTRY_FLAGS[o.country]} {COUNTRY_LABELS[o.country]}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-semibold tabular-nums text-foreground">
                          {formatMoney(o.base_amount, base)}
                        </p>
                        {o.currency !== base && (
                          <p className="text-xs text-muted-foreground">{formatMoney(o.amount, o.currency)}</p>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
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
