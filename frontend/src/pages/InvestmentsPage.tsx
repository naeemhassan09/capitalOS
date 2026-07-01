import { Fragment, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import {
  Plus,
  Pencil,
  Trash2,
  LineChart,
  TrendingUp,
  Info,
  RefreshCw,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import {
  useHoldings,
  useCreateHolding,
  useUpdateHolding,
  useDeleteHolding,
  useAddValuation,
  useSyncPrices,
} from '@/api/holdings';
import { useAccounts } from '@/api/accounts';
import { useExchangeRates } from '@/api/exchangeRates';
import { useDashboard } from '@/api/dashboard';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { formatMoney, formatMoneyCompact, formatPercent, num, SUPPORTED_CURRENCIES } from '@/utils/money';
import { formatDate, todayISO } from '@/utils/date';
import { ASSET_CLASS_LABELS, LIQUIDITY_LABELS } from '@/utils/labels';
import { categoricalPalette, chartColors } from '@/components/charts';
import { PageHeader } from '@/components/PageHeader';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Alert } from '@/components/ui/Alert';
import { Dialog } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Field } from '@/components/ui/Label';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { MetricCard } from '@/components/MetricCard';
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
import { SkeletonTable } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { EmptyState } from '@/components/ui/EmptyState';
import type { Holding, AssetClass, LiquidityClass, Currency, ExchangeRate } from '@/types';

const ASSET_CLASSES = Object.keys(ASSET_CLASS_LABELS) as AssetClass[];
const LIQUIDITY_CLASSES = Object.keys(LIQUIDITY_LABELS) as LiquidityClass[];

const holdingSchema = z.object({
  asset_name: z.string().min(1, 'Required'),
  ticker: z.string().optional(),
  asset_class: z.enum([
    'cash', 'stock', 'etf', 'mutual_fund', 'pension',
    'crypto', 'commodity', 'property', 'private_equity', 'other',
  ]),
  quantity: z.coerce.number(),
  native_currency: z.enum(['EUR', 'PKR', 'USD', 'GBP', 'SAR']),
  cost_basis: z.coerce.number(),
  latest_valuation: z.coerce.number().optional(),
  liquidity_class: z.enum(['immediate', 'short_term', 'restricted', 'illiquid']),
  include_in_net_worth: z.boolean(),
});
type HoldingFormValues = z.infer<typeof holdingSchema>;

const gainLoss = (h: Holding) => num(h.latest_valuation ?? 0) - num(h.cost_basis);

/**
 * Build a converter that maps a native amount to the user's base currency
 * using the user's own ExchangeRate rows. A row means "1 base_currency = rate
 * quote_currency" (mirroring the backend). To convert an amount in currency C
 * to base B:
 *   - C === B                        → factor 1
 *   - row (base=B, quote=C) exists   → divide by rate  (B per C)
 *   - row (base=C, quote=B) exists   → multiply by rate (C per B, inverted)
 *   - otherwise triangulate C → base → B via any pivot currency
 * If no path exists, the amount is returned unchanged and `ok` is false so the
 * caller can skip it from base-currency totals rather than emit NaN.
 */
function makeConverter(rates: ExchangeRate[], base: Currency) {
  // factor(from, to): how many `to` units equal one `from` unit, or null.
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
    // Triangulate through every known pivot currency.
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

const OTHER_SECTION_KEY = '__other__';

export function InvestmentsPage() {
  const holdings = useHoldings();
  const accounts = useAccounts();
  const exchangeRates = useExchangeRates();
  const dashboard = useDashboard();
  const syncPrices = useSyncPrices();
  const toast = useToast();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Holding | null>(null);
  const [deleting, setDeleting] = useState<Holding | null>(null);
  const [valuing, setValuing] = useState<Holding | null>(null);
  // Collapsed portfolio sections, keyed by account id (or OTHER_SECTION_KEY).
  // Default: everything expanded; nothing persisted.
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const rows = holdings.data ?? [];
  const colors = chartColors();
  const palette = categoricalPalette();

  const runPriceSync = async () => {
    try {
      const res = await syncPrices.mutateAsync();
      toast.success(
        'Prices synced',
        `${res.updated.length} updated, ${res.skipped.length} skipped`,
      );
      for (const e of res.errors) {
        toast.error(`Price sync failed: ${e.name}`, e.error);
      }
    } catch (err) {
      toast.error('Price sync failed', err instanceof ApiError ? err.message : undefined);
    }
  };

  const baseCurrency: Currency = dashboard.data?.base_currency ?? 'EUR';
  const convert = useMemo(
    () => makeConverter(exchangeRates.data ?? [], baseCurrency),
    [exchangeRates.data, baseCurrency],
  );

  // Aggregate cards are in base currency; holdings in currencies with no known
  // conversion path are skipped from base totals rather than producing NaN.
  const totals = useMemo(() => {
    let cost = 0;
    let value = 0;
    for (const h of rows) {
      const nativeCost = num(h.cost_basis);
      const nativeValue = num(h.latest_valuation ?? h.cost_basis);
      const c = convert(nativeCost, h.native_currency);
      const v = convert(nativeValue, h.native_currency);
      if (c.ok) cost += c.value;
      if (v.ok) value += v.value;
    }
    return { cost, value, gain: value - cost };
  }, [rows, convert]);

  const byAssetClass = useMemo(() => {
    const map = new Map<string, number>();
    for (const h of rows) {
      const native = num(h.latest_valuation ?? h.cost_basis);
      const v = convert(native, h.native_currency);
      if (!v.ok) continue;
      const label = ASSET_CLASS_LABELS[h.asset_class];
      map.set(label, (map.get(label) ?? 0) + v.value);
    }
    return Array.from(map, ([name, value]) => ({ name, value })).filter((d) => num(d.value) > 0);
  }, [rows, convert]);

  const byCurrency = useMemo(() => {
    const map = new Map<string, number>();
    for (const h of rows) {
      const native = num(h.latest_valuation ?? h.cost_basis);
      const v = convert(native, h.native_currency);
      if (!v.ok) continue;
      map.set(h.native_currency, (map.get(h.native_currency) ?? 0) + v.value);
    }
    return Array.from(map, ([name, value]) => ({ name, value })).filter((d) => num(d.value) > 0);
  }, [rows, convert]);

  // Group holdings into portfolio sections by account_id. Sections follow the
  // accounts list order; holdings with no / unknown account go to "Other
  // holdings", always last.
  const sections = useMemo(() => {
    const accountList = accounts.data ?? [];
    const byAccount = new Map<string, Holding[]>();
    const other: Holding[] = [];
    const knownIds = new Set(accountList.map((a) => a.id));
    for (const h of rows) {
      if (h.account_id && knownIds.has(h.account_id)) {
        const list = byAccount.get(h.account_id);
        if (list) list.push(h);
        else byAccount.set(h.account_id, [h]);
      } else {
        other.push(h);
      }
    }
    const result: { key: string; name: string; holdings: Holding[] }[] = [];
    for (const a of accountList) {
      const hs = byAccount.get(a.id);
      if (hs?.length) result.push({ key: a.id, name: a.name, holdings: hs });
    }
    if (other.length) result.push({ key: OTHER_SECTION_KEY, name: 'Other holdings', holdings: other });
    return result;
  }, [rows, accounts.data]);

  const toggleSection = (key: string) =>
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Investments"
        description="Holdings, allocation and gain/loss."
        actions={
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={runPriceSync}
              loading={syncPrices.isPending}
            >
              <RefreshCw className="h-4 w-4" /> Sync prices
            </Button>
            <Button
              size="sm"
              onClick={() => {
                setEditing(null);
                setFormOpen(true);
              }}
            >
              <Plus className="h-4 w-4" /> New holding
            </Button>
          </div>
        }
      />

      <Alert variant="info" title="Valuation updates" icon>
        Holdings with a ticker + quantity update automatically; others are manual. Update manual
        valuations to keep net worth accurate.
      </Alert>

      {holdings.isLoading ? (
        <Card>
          <CardContent className="pt-4">
            <SkeletonTable rows={6} cols={6} />
          </CardContent>
        </Card>
      ) : holdings.isError ? (
        <ErrorState error={holdings.error} onRetry={() => holdings.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<LineChart className="h-10 w-10" />}
          title="No holdings yet"
          description="Add equities, funds, crypto, property or other assets to track allocation and gain/loss."
          action={
            <Button
              onClick={() => {
                setEditing(null);
                setFormOpen(true);
              }}
            >
              <Plus className="h-4 w-4" /> New holding
            </Button>
          }
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <MetricCard label="Total cost basis" value={formatMoneyCompact(totals.cost, baseCurrency)} tone="muted" />
            <MetricCard label="Total valuation" value={formatMoneyCompact(totals.value, baseCurrency)} icon={<TrendingUp className="h-5 w-5" />} />
            <MetricCard
              label="Unrealised gain/loss"
              value={formatMoney(totals.gain, baseCurrency, { signDisplay: 'always' })}
              tone={totals.gain < 0 ? 'negative' : 'positive'}
              sub={totals.cost > 0 ? formatPercent(totals.gain / totals.cost) : undefined}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <AllocationChart title="Asset allocation" data={byAssetClass} currency={baseCurrency} palette={palette} colors={colors} />
            <AllocationChart title="Currency allocation" data={byCurrency} currency={baseCurrency} palette={palette} colors={colors} />
          </div>

          <TableContainer>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Asset</TableHead>
                  <TableHead>Class</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead className="text-right">Cost basis</TableHead>
                  <TableHead className="text-right">Valuation</TableHead>
                  <TableHead className="text-right">Gain/Loss</TableHead>
                  <TableHead>Liquidity</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sections.length === 0 ? (
                  <TableEmpty colSpan={8}>No holdings.</TableEmpty>
                ) : (
                  sections.map((section) => {
                    const isCollapsed = !!collapsed[section.key];
                    // Section subtotals: native shown only when every holding
                    // shares one currency; base subtotal uses the page's
                    // converter (skipping unconvertible amounts, like totals).
                    const currencies = new Set(section.holdings.map((h) => h.native_currency));
                    const uniformCurrency =
                      currencies.size === 1 ? section.holdings[0].native_currency : null;
                    let nativeValue = 0;
                    let baseValue = 0;
                    let gainNative = 0;
                    let gainBase = 0;
                    for (const h of section.holdings) {
                      const nv = num(h.latest_valuation ?? h.cost_basis);
                      nativeValue += nv;
                      const v = convert(nv, h.native_currency);
                      if (v.ok) baseValue += v.value;
                      if (h.latest_valuation != null && h.cost_basis != null) {
                        const g = num(h.latest_valuation) - num(h.cost_basis);
                        gainNative += g;
                        const gc = convert(g, h.native_currency);
                        if (gc.ok) gainBase += gc.value;
                      }
                    }
                    const gain = uniformCurrency ? gainNative : gainBase;
                    const gainCurrency = uniformCurrency ?? baseCurrency;
                    return (
                      <Fragment key={section.key}>
                        <TableRow
                          data-portfolio-section={section.key}
                          aria-expanded={!isCollapsed}
                          className="cursor-pointer bg-muted/40 hover:bg-muted/60"
                          onClick={() => toggleSection(section.key)}
                        >
                          <TableCell colSpan={8} className="py-2">
                            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                              <span className="flex items-center gap-2 font-semibold text-foreground">
                                {isCollapsed ? (
                                  <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                                ) : (
                                  <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                                )}
                                {section.name}
                                <Badge variant="secondary">
                                  {section.holdings.length}{' '}
                                  {section.holdings.length === 1 ? 'holding' : 'holdings'}
                                </Badge>
                              </span>
                              <span className="ml-auto flex flex-wrap items-center justify-end gap-x-4 gap-y-1 tabular-nums">
                                {uniformCurrency && (
                                  <span className="font-medium text-foreground">
                                    {formatMoney(nativeValue, uniformCurrency)}
                                  </span>
                                )}
                                {uniformCurrency !== baseCurrency && (
                                  <span className="text-muted-foreground">
                                    ≈ {formatMoney(baseValue, baseCurrency)}
                                  </span>
                                )}
                                <span
                                  className={
                                    gain < 0 ? 'font-medium text-negative' : 'font-medium text-positive'
                                  }
                                >
                                  {formatMoney(gain, gainCurrency, { signDisplay: 'always' })}
                                </span>
                              </span>
                            </div>
                          </TableCell>
                        </TableRow>
                        {!isCollapsed &&
                          section.holdings.map((h) => {
                            const gl = gainLoss(h);
                            return (
                              <TableRow key={h.id} data-holding-row={section.key}>
                                <TableCell>
                                  <div className="min-w-[140px] pl-6">
                                    <p className="font-medium text-foreground">{h.asset_name}</p>
                                    {h.ticker && <p className="text-xs text-muted-foreground">{h.ticker}</p>}
                                  </div>
                                </TableCell>
                                <TableCell>
                                  <Badge variant="secondary">{ASSET_CLASS_LABELS[h.asset_class]}</Badge>
                                </TableCell>
                                <TableCell className="text-right tabular-nums">{num(h.quantity)}</TableCell>
                                <TableCell className="text-right tabular-nums">
                                  {formatMoney(h.cost_basis, h.native_currency)}
                                </TableCell>
                                <TableCell className="text-right tabular-nums">
                                  {h.latest_valuation != null ? (
                                    <span title={h.valuation_date ? `As of ${formatDate(h.valuation_date)}` : undefined}>
                                      {formatMoney(h.latest_valuation, h.native_currency)}
                                      {h.valuation_is_manual === false && (
                                        <span className="ml-1.5 rounded-full bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                                          auto
                                        </span>
                                      )}
                                    </span>
                                  ) : (
                                    <span className="text-muted-foreground">—</span>
                                  )}
                                </TableCell>
                                <TableCell
                                  className={
                                    gl < 0
                                      ? 'text-right font-medium tabular-nums text-negative'
                                      : 'text-right font-medium tabular-nums text-positive'
                                  }
                                >
                                  {formatMoney(gl, h.native_currency, { signDisplay: 'always' })}
                                </TableCell>
                                <TableCell>
                                  <Badge variant={h.liquidity_class === 'illiquid' ? 'illiquid' : 'invested'}>
                                    {LIQUIDITY_LABELS[h.liquidity_class]}
                                  </Badge>
                                </TableCell>
                                <TableCell>
                                  <div className="flex justify-end gap-1">
                                    <Button variant="ghost" size="sm" onClick={() => setValuing(h)} title="Add valuation">
                                      <TrendingUp className="h-4 w-4" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="h-8 w-8"
                                      onClick={() => {
                                        setEditing(h);
                                        setFormOpen(true);
                                      }}
                                      aria-label="Edit"
                                    >
                                      <Pencil className="h-4 w-4" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="h-8 w-8 text-danger"
                                      onClick={() => setDeleting(h)}
                                      aria-label="Delete"
                                    >
                                      <Trash2 className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </TableCell>
                              </TableRow>
                            );
                          })}
                      </Fragment>
                    );
                  })
                )}
                {sections.length > 0 && (
                  <TableRow className="border-t-2 border-border bg-muted/50 font-semibold hover:bg-muted/50">
                    <TableCell colSpan={3}>Total ({baseCurrency})</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatMoney(totals.cost, baseCurrency)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatMoney(totals.value, baseCurrency)}
                    </TableCell>
                    <TableCell
                      className={
                        totals.gain < 0
                          ? 'text-right tabular-nums text-negative'
                          : 'text-right tabular-nums text-positive'
                      }
                    >
                      {formatMoney(totals.gain, baseCurrency, { signDisplay: 'always' })}
                    </TableCell>
                    <TableCell colSpan={2} />
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      <HoldingFormDialog open={formOpen} onClose={() => setFormOpen(false)} holding={editing} />
      <ValuationDialog holding={valuing} onClose={() => setValuing(null)} />
      <DeleteHoldingDialog holding={deleting} onClose={() => setDeleting(null)} />
    </div>
  );
}

function AllocationChart({
  title,
  data,
  currency,
  palette,
  colors,
}: {
  title: string;
  data: { name: string; value: number }[];
  currency: Currency;
  palette: string[];
  colors: ReturnType<typeof chartColors>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <EmptyState title="No data" className="border-0" />
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={data} dataKey="value" nameKey="name" innerRadius={50} outerRadius={88} paddingAngle={2}>
                  {data.map((_, i) => (
                    <Cell key={i} fill={palette[i % palette.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v: number, n) => [formatMoneyCompact(num(v), currency), n as string]}
                  contentStyle={{
                    background: 'hsl(var(--popover))',
                    border: `1px solid ${colors.grid}`,
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function HoldingFormDialog({
  open,
  onClose,
  holding,
}: {
  open: boolean;
  onClose: () => void;
  holding: Holding | null;
}) {
  const create = useCreateHolding();
  const update = useUpdateHolding();
  const toast = useToast();
  const isEdit = !!holding;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<HoldingFormValues>({
    resolver: zodResolver(holdingSchema),
    values: {
      asset_name: holding?.asset_name ?? '',
      ticker: holding?.ticker ?? '',
      asset_class: holding?.asset_class ?? 'stock',
      quantity: holding?.quantity ?? 0,
      native_currency: (holding?.native_currency ?? 'EUR') as Currency,
      cost_basis: holding?.cost_basis ?? 0,
      latest_valuation: holding?.latest_valuation ?? undefined,
      liquidity_class: holding?.liquidity_class ?? 'immediate',
      include_in_net_worth: holding?.include_in_net_worth ?? true,
    },
  });

  const isProperty = holding?.asset_class === 'property';

  const onSubmit = handleSubmit(async (values) => {
    const payload = { ...values, ticker: values.ticker || null };
    try {
      if (isEdit && holding) {
        await update.mutateAsync({ id: holding.id, ...payload });
        toast.success('Holding updated');
      } else {
        await create.mutateAsync(payload);
        toast.success('Holding created');
      }
      onClose();
    } catch (err) {
      toast.error('Save failed', err instanceof ApiError ? err.message : undefined);
    }
  });

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={isEdit ? 'Edit holding' : 'New holding'}
      size="lg"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={onSubmit} loading={create.isPending || update.isPending}>
            {isEdit ? 'Save' : 'Create'}
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Asset name" required error={errors.asset_name?.message}>
            <Input invalid={!!errors.asset_name} {...register('asset_name')} />
          </Field>
          <Field label="Ticker" hint="e.g. AAPL.US (stooq), PSX:MEBL, MUFAP:Meezan Rozana">
            <Input {...register('ticker')} />
          </Field>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="Asset class" required>
            <Select {...register('asset_class')}>
              {ASSET_CLASSES.map((c) => (
                <option key={c} value={c}>
                  {ASSET_CLASS_LABELS[c]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Quantity" required>
            <Input type="number" step="any" {...register('quantity')} />
          </Field>
          <Field label="Currency" required>
            <Select {...register('native_currency')}>
              {SUPPORTED_CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Cost basis" required>
            <Input type="number" step="0.01" {...register('cost_basis')} />
          </Field>
          <Field label="Latest valuation" hint="Manual value">
            <Input type="number" step="0.01" {...register('latest_valuation')} />
          </Field>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Liquidity" required>
            <Select {...register('liquidity_class')}>
              {LIQUIDITY_CLASSES.map((c) => (
                <option key={c} value={c}>
                  {LIQUIDITY_LABELS[c]}
                </option>
              ))}
            </Select>
          </Field>
          <label className="flex cursor-pointer items-center gap-2 self-end rounded-md border border-border p-2.5 text-sm">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-input text-primary focus-ring"
              {...register('include_in_net_worth')}
            />
            Include in net worth
          </label>
        </div>
        {isProperty && (
          <p className="flex items-start gap-2 text-xs text-muted-foreground">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            Property is typically illiquid — toggle "Include in net worth" to control whether it counts toward
            deployable capital.
          </p>
        )}
      </form>
    </Dialog>
  );
}

const valuationSchema = z.object({
  valuation_date: z.string().min(1, 'Required'),
  valuation: z.coerce.number(),
  unit_price: z.coerce.number().optional(),
});
type ValuationValues = z.infer<typeof valuationSchema>;

function ValuationDialog({ holding, onClose }: { holding: Holding | null; onClose: () => void }) {
  const add = useAddValuation();
  const toast = useToast();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ValuationValues>({
    resolver: zodResolver(valuationSchema),
    values: {
      valuation_date: todayISO(),
      valuation: holding?.latest_valuation ?? 0,
      unit_price: undefined,
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    if (!holding) return;
    try {
      await add.mutateAsync({ id: holding.id, ...values });
      toast.success('Valuation recorded');
      onClose();
    } catch (err) {
      toast.error('Save failed', err instanceof ApiError ? err.message : undefined);
    }
  });

  return (
    <Dialog
      open={!!holding}
      onClose={onClose}
      title="Add valuation"
      description={holding ? `${holding.asset_name} (${holding.native_currency})` : undefined}
      size="sm"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={onSubmit} loading={add.isPending}>
            Save valuation
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Date" required error={errors.valuation_date?.message}>
          <Input type="date" {...register('valuation_date')} />
        </Field>
        <Field label="Total valuation" required error={errors.valuation?.message}>
          <Input type="number" step="0.01" {...register('valuation')} />
        </Field>
        <Field label="Unit price" hint="Optional">
          <Input type="number" step="any" {...register('unit_price')} />
        </Field>
      </form>
    </Dialog>
  );
}

function DeleteHoldingDialog({ holding, onClose }: { holding: Holding | null; onClose: () => void }) {
  const del = useDeleteHolding();
  const toast = useToast();
  return (
    <ConfirmDialog
      open={!!holding}
      onClose={onClose}
      title="Delete holding?"
      description={holding ? `"${holding.asset_name}" will be removed.` : ''}
      confirmLabel="Delete"
      confirmVariant="destructive"
      loading={del.isPending}
      onConfirm={async () => {
        if (!holding) return;
        try {
          await del.mutateAsync(holding.id);
          toast.success('Holding deleted');
          onClose();
        } catch (err) {
          toast.error('Delete failed', err instanceof ApiError ? err.message : undefined);
        }
      }}
    />
  );
}
