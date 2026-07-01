import { useEffect, useState } from 'react';
import { Plus, Trash2, Pencil, ArrowLeftRight, RefreshCw } from 'lucide-react';
import {
  useExchangeRates,
  useCreateExchangeRate,
  useUpdateExchangeRate,
  useDeleteExchangeRate,
  useConvert,
  useSyncExchangeRates,
} from '@/api/exchangeRates';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { SUPPORTED_CURRENCIES, formatMoney } from '@/utils/money';
import { formatDate, todayISO } from '@/utils/date';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Field } from '@/components/ui/Label';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
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
import type { ExchangeRate, Currency } from '@/types';

export function ExchangeRatesSection() {
  const rates = useExchangeRates();
  const del = useDeleteExchangeRate();
  const sync = useSyncExchangeRates();
  const toast = useToast();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ExchangeRate | null>(null);
  const [deleting, setDeleting] = useState<ExchangeRate | null>(null);

  const runSync = async () => {
    try {
      const res = await sync.mutateAsync();
      const skipped = res.skipped_manual.length
        ? ` (manual kept: ${res.skipped_manual.join(', ')})`
        : '';
      toast.success(
        `Rates synced from ${res.source}`,
        `${res.base_currency} → ${res.updated.join(', ')}${skipped}`,
      );
    } catch (err) {
      toast.error('Sync failed', err instanceof ApiError ? err.message : undefined);
    }
  };

  return (
    <div className="space-y-6">
      <ConverterCard />
      <Card>
        <CardHeader className="flex-row items-start justify-between">
          <div>
            <CardTitle>Exchange rates</CardTitle>
            <CardDescription>
              Auto-synced daily from a free market feed; manual rates for the same day
              always win. Historical rates are never rewritten.
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={runSync} loading={sync.isPending}>
              <RefreshCw className="h-4 w-4" /> Sync now
            </Button>
            <Button size="sm" onClick={() => { setEditing(null); setFormOpen(true); }}>
              <Plus className="h-4 w-4" /> Add rate
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {rates.isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : (
            <TableContainer>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Pair</TableHead>
                    <TableHead className="text-right">Rate</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(rates.data ?? []).length === 0 ? (
                    <TableEmpty colSpan={5}>No rates defined.</TableEmpty>
                  ) : (
                    (rates.data ?? []).map((r) => (
                      <TableRow key={r.id}>
                        <TableCell className="font-medium text-foreground">
                          {r.base_currency} → {r.quote_currency}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{r.rate}</TableCell>
                        <TableCell>{formatDate(r.rate_date)}</TableCell>
                        <TableCell>
                          {r.is_manual ? <Badge variant="secondary">Manual</Badge> : <Badge variant="info">{r.source ?? 'Auto'}</Badge>}
                        </TableCell>
                        <TableCell>
                          <div className="flex justify-end gap-1">
                            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => { setEditing(r); setFormOpen(true); }} aria-label="Edit">
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8 text-danger" onClick={() => setDeleting(r)} aria-label="Delete">
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      <RateFormDialog open={formOpen} onClose={() => setFormOpen(false)} rate={editing} />
      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Delete rate?"
        description={deleting ? `${deleting.base_currency} → ${deleting.quote_currency} will be removed.` : ''}
        confirmLabel="Delete"
        confirmVariant="destructive"
        loading={del.isPending}
        onConfirm={async () => {
          if (!deleting) return;
          try {
            await del.mutateAsync(deleting.id);
            toast.success('Rate deleted');
            setDeleting(null);
          } catch (err) {
            toast.error('Delete failed', err instanceof ApiError ? err.message : undefined);
          }
        }}
      />
    </div>
  );
}

function ConverterCard() {
  const convert = useConvert();
  const [amount, setAmount] = useState(100);
  const [from, setFrom] = useState<Currency>('EUR');
  const [to, setTo] = useState<Currency>('PKR');
  const [result, setResult] = useState<string | null>(null);
  const toast = useToast();

  const run = async () => {
    try {
      const res = await convert.mutateAsync({ amount, from, to });
      setResult(`${formatMoney(amount, from)} = ${formatMoney(res.converted, to)} @ ${res.rate}`);
    } catch (err) {
      toast.error('Conversion failed', err instanceof ApiError ? err.message : undefined);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ArrowLeftRight className="h-5 w-5" /> Quick convert
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Amount" className="w-32">
            <Input type="number" value={amount} onChange={(e) => setAmount(Number(e.target.value) || 0)} />
          </Field>
          <Field label="From" className="w-28">
            <Select value={from} onChange={(e) => setFrom(e.target.value as Currency)}>
              {SUPPORTED_CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="To" className="w-28">
            <Select value={to} onChange={(e) => setTo(e.target.value as Currency)}>
              {SUPPORTED_CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </Field>
          <Button onClick={run} loading={convert.isPending}>
            Convert
          </Button>
        </div>
        {result && <p className="mt-3 text-sm font-medium text-foreground">{result}</p>}
      </CardContent>
    </Card>
  );
}

function RateFormDialog({ open, onClose, rate }: { open: boolean; onClose: () => void; rate: ExchangeRate | null }) {
  const create = useCreateExchangeRate();
  const update = useUpdateExchangeRate();
  const toast = useToast();
  const isEdit = !!rate;
  const [form, setForm] = useState({
    base_currency: 'EUR' as Currency,
    quote_currency: 'PKR' as Currency,
    rate: 0,
    rate_date: todayISO(),
    source: '',
  });

  useEffect(() => {
    if (!open) return;
    setForm({
      base_currency: (rate?.base_currency ?? 'EUR') as Currency,
      quote_currency: (rate?.quote_currency ?? 'PKR') as Currency,
      rate: rate?.rate ?? 0,
      rate_date: rate?.rate_date ?? todayISO(),
      source: rate?.source ?? '',
    });
  }, [open, rate]);

  const submit = async () => {
    const payload = { ...form, source: form.source || null, is_manual: true };
    try {
      if (isEdit && rate) {
        await update.mutateAsync({ id: rate.id, ...payload });
        toast.success('Rate updated');
      } else {
        await create.mutateAsync(payload);
        toast.success('Rate added');
      }
      onClose();
    } catch (err) {
      toast.error('Save failed', err instanceof ApiError ? err.message : undefined);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={isEdit ? 'Edit rate' : 'Add rate'}
      size="sm"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} loading={create.isPending || update.isPending}>
            {isEdit ? 'Save' : 'Add'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Base">
            <Select value={form.base_currency} onChange={(e) => setForm((f) => ({ ...f, base_currency: e.target.value as Currency }))}>
              {SUPPORTED_CURRENCIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </Select>
          </Field>
          <Field label="Quote">
            <Select value={form.quote_currency} onChange={(e) => setForm((f) => ({ ...f, quote_currency: e.target.value as Currency }))}>
              {SUPPORTED_CURRENCIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </Select>
          </Field>
        </div>
        <Field label="Rate" required hint="1 base = rate × quote">
          <Input type="number" step="any" value={form.rate} onChange={(e) => setForm((f) => ({ ...f, rate: Number(e.target.value) || 0 }))} />
        </Field>
        <Field label="Date">
          <Input type="date" value={form.rate_date} onChange={(e) => setForm((f) => ({ ...f, rate_date: e.target.value }))} />
        </Field>
        <Field label="Source" hint="Optional">
          <Input value={form.source} onChange={(e) => setForm((f) => ({ ...f, source: e.target.value }))} />
        </Field>
      </div>
    </Dialog>
  );
}
