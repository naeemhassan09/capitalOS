import { useMemo } from 'react';
import { Landmark, Coins, ShieldCheck, TrendingDown, Wallet } from 'lucide-react';
import { useAccounts } from '@/api/accounts';
import { useHoldings } from '@/api/holdings';
import { useReserves } from '@/api/reserves';
import { useExchangeRates } from '@/api/exchangeRates';
import { useDashboard } from '@/api/dashboard';
import { formatMoney, formatMoneyCompact, num } from '@/utils/money';
import {
  ACCOUNT_TYPE_LABELS,
  ASSET_CLASS_LABELS,
  COUNTRY_LABELS,
  COUNTRY_FLAGS,
  LIABILITY_TYPES,
} from '@/utils/labels';
import { PageHeader } from '@/components/PageHeader';
import { MetricCard } from '@/components/MetricCard';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { SkeletonCards } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { EmptyState } from '@/components/ui/EmptyState';
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
import type { Account, Holding, Currency, ExchangeRate, Country } from '@/types';

const COUNTRY_ORDER: Country[] = ['IE', 'PK', 'OTHER'];

/**
 * Build a converter that maps a native amount to the user's base currency
 * using the user's own ExchangeRate rows. A row means "1 base_currency = rate
 * quote_currency" (mirroring the backend). Mirrors InvestmentsPage.makeConverter:
 * if no conversion path exists, the amount is returned unchanged and `ok` is
 * false so callers can skip it from base totals rather than emit NaN.
 */
function makeConverter(rates: ExchangeRate[], base: Currency) {
  const direct = (from: Currency, to: Currency): number | null => {
    if (from === to) return 1;
    const fwd = rates.find((r) => r.base_currency === to && r.quote_currency === from);
    if (fwd && num(fwd.rate) > 0) return 1 / num(fwd.rate); // to per from
    const inv = rates.find((r) => r.base_currency === from && r.quote_currency === to);
    if (inv && num(inv.rate) > 0) return num(inv.rate); // to per from
    return null;
  };

  const factor = (from: Currency, to: Currency): number | null => {
    const d = direct(from, to);
    if (d != null) return d;
    const pivots = new Set<Currency>();
    for (const r of rates) {
      pivots.add(r.base_currency);
      pivots.add(r.quote_currency);
    }
    for (const pivot of pivots) {
      if (pivot === from || pivot === to) continue;
      const a = direct(from, pivot);
      const b = direct(pivot, to);
      if (a != null && b != null) return a * b;
    }
    return null;
  };

  return (amount: number, from: Currency): { value: number; ok: boolean } => {
    const f = factor(from, base);
    if (f == null) return { value: amount, ok: false };
    return { value: amount * f, ok: true };
  };
}

// A single line in the consolidated asset register.
interface AssetRow {
  key: string;
  name: string;
  detail: string; // account type / asset class label
  country: Country;
  currency: Currency;
  nativeAmount: number;
  baseValue: number;
  baseOk: boolean;
  isReserve: boolean;
}

export function NetWorthPage() {
  const accounts = useAccounts();
  const holdings = useHoldings();
  const reserves = useReserves();
  const exchangeRates = useExchangeRates();
  const dashboard = useDashboard();

  const base: Currency = dashboard.data?.base_currency ?? 'EUR';
  const convert = useMemo(
    () => makeConverter(exchangeRates.data ?? [], base),
    [exchangeRates.data, base],
  );

  // Consolidated asset register: accounts with a positive balance first, then
  // holdings. Liabilities and archived / excluded accounts are left out — this
  // register is "everything you own". Grouped by country.
  const assetRows = useMemo<AssetRow[]>(() => {
    const rows: AssetRow[] = [];

    const accountList = (accounts.data ?? []).filter(
      (a: Account) =>
        !a.is_archived &&
        a.include_in_net_worth &&
        !LIABILITY_TYPES.has(a.account_type) &&
        num(a.current_balance) > 0,
    );
    for (const a of accountList) {
      const native = num(a.current_balance);
      const conv = convert(native, a.currency);
      rows.push({
        key: `acc-${a.id}`,
        name: a.name,
        detail: ACCOUNT_TYPE_LABELS[a.account_type],
        country: a.country,
        currency: a.currency,
        nativeAmount: native,
        baseValue: conv.value,
        baseOk: conv.ok,
        isReserve: a.is_protected_reserve,
      });
    }

    const holdingList = (holdings.data ?? []).filter(
      (h: Holding) => h.include_in_net_worth && num(h.latest_valuation ?? h.cost_basis) > 0,
    );
    for (const h of holdingList) {
      const native = num(h.latest_valuation ?? h.cost_basis);
      const conv = convert(native, h.native_currency);
      rows.push({
        // Holdings carry no jurisdiction on the backend; file them under Other.
        key: `hold-${h.id}`,
        name: h.asset_name,
        detail: ASSET_CLASS_LABELS[h.asset_class],
        country: 'OTHER',
        currency: h.native_currency,
        nativeAmount: native,
        baseValue: conv.value,
        baseOk: conv.ok,
        isReserve: false,
      });
    }

    return rows;
  }, [accounts.data, holdings.data, convert]);

  const groupedRows = useMemo(() => {
    const map = new Map<Country, AssetRow[]>();
    for (const row of assetRows) {
      // Accounts before holdings, then descending base value within a country.
      if (!map.has(row.country)) map.set(row.country, []);
      map.get(row.country)!.push(row);
    }
    for (const list of map.values()) {
      list.sort((a, b) => {
        const aAcc = a.key.startsWith('acc-') ? 0 : 1;
        const bAcc = b.key.startsWith('acc-') ? 0 : 1;
        if (aAcc !== bAcc) return aAcc - bAcc;
        return b.baseValue - a.baseValue;
      });
    }
    return map;
  }, [assetRows]);

  // Total assets in base (skip rows with no conversion path so we never sum NaN).
  const totalAssetsBase = useMemo(
    () => assetRows.reduce((sum, r) => (r.baseOk ? sum + r.baseValue : sum), 0),
    [assetRows],
  );

  const grandTotalBase = totalAssetsBase;

  // Dashboard figures — used for the deployable reconciliation so it ties out
  // exactly with the rest of the app rather than re-deriving from raw rows.
  const protectedReservesBase = num(dashboard.data?.protected_reserves_base);
  const liabilitiesBase = num(dashboard.data?.current_liabilities_base);
  const committedBase = useMemo(() => {
    let sum = 0;
    for (const j of dashboard.data?.deployable.by_jurisdiction ?? []) {
      sum += Math.abs(num(j.committed_expenses_base));
    }
    return sum;
  }, [dashboard.data]);
  const deployableTotal = num(dashboard.data?.deployable.total_base);
  const deployableNegative = deployableTotal < 0;
  // Liabilities + committed obligations, expressed as a single positive figure.
  const liabilitiesAndCommitted = Math.abs(liabilitiesBase) + committedBase;

  const isLoading =
    accounts.isLoading || holdings.isLoading || reserves.isLoading || dashboard.isLoading;
  const isError = accounts.isError || holdings.isError || dashboard.isError;

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Net Worth" />
        <SkeletonCards count={4} />
        <SkeletonCards count={1} />
      </div>
    );
  }

  if (isError) {
    const err = accounts.error ?? holdings.error ?? dashboard.error;
    return (
      <div className="space-y-6">
        <PageHeader title="Net Worth" />
        <ErrorState
          error={err}
          onRetry={() => {
            accounts.refetch();
            holdings.refetch();
            dashboard.refetch();
          }}
        />
      </div>
    );
  }

  const reserveList = reserves.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Net Worth"
        description={`Everything you own, in ${base}. Reserves are assets but ring-fenced — not deployable.`}
      />

      {/* Summary metrics — all base currency */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Total assets"
          value={formatMoney(totalAssetsBase, base)}
          tone="positive"
          icon={<Wallet className="h-5 w-5" />}
          sub="Accounts + holdings you own"
        />
        <MetricCard
          label="Protected reserves"
          value={formatMoney(protectedReservesBase, base)}
          tone="protected"
          icon={<ShieldCheck className="h-5 w-5" />}
          sub="Ring-fenced, not deployable"
        />
        <MetricCard
          label="Liabilities + committed"
          value={formatMoney(liabilitiesAndCommitted, base)}
          tone="negative"
          icon={<TrendingDown className="h-5 w-5" />}
          sub={`Liab. ${formatMoneyCompact(Math.abs(liabilitiesBase), base)} · Committed ${formatMoneyCompact(
            committedBase,
            base,
          )}`}
        />
        <MetricCard
          prominent
          tone={deployableNegative ? 'negative' : 'deployable'}
          label="True deployable capital"
          value={formatMoney(deployableTotal, base)}
          icon={<Coins className="h-5 w-5" />}
          sub={
            deployableNegative
              ? 'Below required reserves — do not treat as available'
              : 'What is actually free to deploy'
          }
        />
      </div>

      {/* Assets → deployable breakdown, using dashboard figures so it ties out */}
      <Card>
        <CardHeader>
          <CardTitle>From assets to deployable capital</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="space-y-2 text-sm">
            <BreakdownRow label="Total assets" value={formatMoney(totalAssetsBase, base)} />
            <BreakdownRow
              label="Less: protected reserves"
              value={formatMoney(-Math.abs(protectedReservesBase), base)}
              muted
            />
            <BreakdownRow
              label="Less: liabilities + committed"
              value={formatMoney(-liabilitiesAndCommitted, base)}
              muted
            />
            <div className="border-t border-border pt-2">
              <BreakdownRow
                label="True deployable capital"
                value={formatMoney(deployableTotal, base)}
                emphasis
                tone={deployableNegative ? 'negative' : 'deployable'}
              />
            </div>
          </dl>
          <p className="mt-3 text-xs text-muted-foreground">
            Deployable capital comes straight from the dashboard so it matches the rest of the app.
            Total assets and deployable are measured differently (e.g. illiquid assets and cash
            timing), so the lines above are an at-a-glance guide rather than an exact subtraction.
          </p>
        </CardContent>
      </Card>

      {/* Consolidated asset register, grouped by country */}
      <Card>
        <CardHeader>
          <CardTitle>All assets</CardTitle>
        </CardHeader>
        <CardContent>
          {assetRows.length === 0 ? (
            <EmptyState
              icon={<Landmark className="h-10 w-10" />}
              title="No assets yet"
              description="Add accounts or holdings to see your consolidated asset register."
              className="border-0"
            />
          ) : (
            <div className="space-y-6">
              {COUNTRY_ORDER.filter((c) => groupedRows.has(c)).map((country) => {
                const rows = groupedRows.get(country)!;
                const subtotal = rows.reduce((s, r) => (r.baseOk ? s + r.baseValue : s), 0);
                return (
                  <div key={country}>
                    <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
                      <span>{COUNTRY_FLAGS[country]}</span> {COUNTRY_LABELS[country]}
                    </h3>
                    <TableContainer>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Asset</TableHead>
                            <TableHead>Type</TableHead>
                            <TableHead className="text-right">Native amount</TableHead>
                            <TableHead className="text-right">Value ({base})</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {rows.length === 0 ? (
                            <TableEmpty colSpan={4}>No assets.</TableEmpty>
                          ) : (
                            rows.map((row) => (
                              <TableRow key={row.key}>
                                <TableCell>
                                  <div className="flex min-w-[160px] flex-wrap items-center gap-2">
                                    <span className="font-medium text-foreground">{row.name}</span>
                                    {row.isReserve && (
                                      <Badge variant="protected">Reserve · not deployable</Badge>
                                    )}
                                  </div>
                                </TableCell>
                                <TableCell>
                                  <Badge variant="secondary">{row.detail}</Badge>
                                </TableCell>
                                <TableCell className="text-right tabular-nums">
                                  {formatMoney(row.nativeAmount, row.currency)}
                                </TableCell>
                                <TableCell className="text-right font-medium tabular-nums text-foreground">
                                  {row.baseOk ? (
                                    formatMoney(row.baseValue, base)
                                  ) : (
                                    <span
                                      className="text-muted-foreground"
                                      title="No exchange rate available to convert this currency"
                                    >
                                      —
                                    </span>
                                  )}
                                </TableCell>
                              </TableRow>
                            ))
                          )}
                        </TableBody>
                        <tfoot className="border-t border-border">
                          <TableRow className="hover:bg-transparent">
                            <TableCell className="font-medium text-muted-foreground" colSpan={3}>
                              {COUNTRY_LABELS[country]} subtotal
                            </TableCell>
                            <TableCell className="text-right font-semibold tabular-nums text-foreground">
                              {formatMoney(subtotal, base)}
                            </TableCell>
                          </TableRow>
                        </tfoot>
                      </Table>
                    </TableContainer>
                  </div>
                );
              })}

              {/* Grand total across all countries */}
              <div className="flex items-center justify-between rounded-lg border border-border bg-muted/40 px-4 py-3">
                <span className="text-sm font-semibold text-foreground">Total assets</span>
                <span className="text-lg font-semibold tabular-nums text-foreground">
                  {formatMoney(grandTotalBase, base)}
                </span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Protected reserves detail */}
      <Card>
        <CardHeader>
          <CardTitle>Protected reserves</CardTitle>
        </CardHeader>
        <CardContent>
          {reserveList.length === 0 ? (
            <EmptyState
              icon={<ShieldCheck className="h-10 w-10" />}
              title="No reserve policies"
              description="Reserve policies ring-fence part of your assets so they are not counted as deployable."
              className="border-0"
            />
          ) : (
            <>
              <TableContainer>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Reserve</TableHead>
                      <TableHead>Jurisdiction</TableHead>
                      <TableHead className="text-right">Protected</TableHead>
                      <TableHead className="text-right">Value ({base})</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {reserveList.map((r) => {
                      const native = num(r.protected_amount);
                      const conv = convert(native, r.currency);
                      return (
                        <TableRow key={r.id}>
                          <TableCell>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-medium text-foreground">{r.name}</span>
                              {r.hard_floor && <Badge variant="warning">Hard floor</Badge>}
                            </div>
                          </TableCell>
                          <TableCell>
                            <span className="text-sm text-muted-foreground">
                              {COUNTRY_FLAGS[r.jurisdiction]} {COUNTRY_LABELS[r.jurisdiction]}
                            </span>
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {formatMoney(native, r.currency)}
                          </TableCell>
                          <TableCell className="text-right font-medium tabular-nums text-foreground">
                            {conv.ok ? (
                              formatMoney(conv.value, base)
                            ) : (
                              <span className="text-muted-foreground">—</span>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
              <p className="mt-3 text-xs text-muted-foreground">
                Held back from deployable capital. Reserves classify balances you already hold — they
                are not added on top of your assets.
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function BreakdownRow({
  label,
  value,
  muted = false,
  emphasis = false,
  tone,
}: {
  label: string;
  value: string;
  muted?: boolean;
  emphasis?: boolean;
  tone?: 'negative' | 'deployable';
}) {
  const valueClass = emphasis
    ? tone === 'negative'
      ? 'text-danger font-semibold'
      : 'text-deployable font-semibold'
    : muted
      ? 'text-muted-foreground'
      : 'text-foreground';
  return (
    <div className="flex items-center justify-between">
      <dt className={emphasis ? 'font-semibold text-foreground' : 'text-muted-foreground'}>
        {label}
      </dt>
      <dd className={`tabular-nums ${valueClass}`}>{value}</dd>
    </div>
  );
}
