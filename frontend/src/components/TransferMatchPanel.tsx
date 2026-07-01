import { useState } from 'react';
import { ArrowRight, Check, X, Link2 } from 'lucide-react';
import { useTransferCandidates, useLinkTransfer } from '@/api/transactions';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { formatMoney, formatPercent } from '@/utils/money';
import { formatDate } from '@/utils/date';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Field } from '@/components/ui/Label';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import type { Currency, TransferCandidate } from '@/types';

export function TransferMatchPanel({ onClose }: { onClose: () => void }) {
  const [days, setDays] = useState(3);
  const [tolerance, setTolerance] = useState(0.02);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const { data, isLoading, isError, refetch } = useTransferCandidates(days, tolerance);
  const link = useLinkTransfer();
  const toast = useToast();

  const candidateKey = (c: TransferCandidate) => `${c.debit.id}-${c.credit.id}`;

  const confirm = async (c: TransferCandidate) => {
    try {
      await link.mutateAsync({ debit_id: c.debit.id, credit_id: c.credit.id });
      toast.success('Transfer linked');
      setDismissed((prev) => new Set(prev).add(candidateKey(c)));
    } catch (err) {
      toast.error('Could not link transfer', err instanceof ApiError ? err.message : undefined);
    }
  };

  const reject = (c: TransferCandidate) => {
    setDismissed((prev) => new Set(prev).add(candidateKey(c)));
  };

  const visible = (data ?? []).filter((c) => !dismissed.has(candidateKey(c)));

  return (
    <Card className="border-primary/30">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Link2 className="h-5 w-5 text-primary" /> Match transfers
        </CardTitle>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close transfer matcher">
          <X className="h-4 w-4" />
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Window (days)" className="w-28">
            <Input
              type="number"
              min={1}
              value={days}
              onChange={(e) => setDays(Math.max(1, Number(e.target.value) || 1))}
            />
          </Field>
          <Field label="FX tolerance" hint="fraction" className="w-32">
            <Input
              type="number"
              step="0.01"
              min={0}
              value={tolerance}
              onChange={(e) => setTolerance(Math.max(0, Number(e.target.value) || 0))}
            />
          </Field>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            Refresh
          </Button>
        </div>

        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : isError ? (
          <p className="text-sm text-danger">Could not load candidates.</p>
        ) : visible.length === 0 ? (
          <EmptyState title="No transfer candidates" description="Nothing to match in this window." className="border-0" />
        ) : (
          <ul className="space-y-3">
            {visible.map((c) => (
              <li key={candidateKey(c)} className="rounded-lg border border-border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={c.confidence >= 0.8 ? 'success' : 'warning'}>
                    {formatPercent(c.confidence, 0)} match
                  </Badge>
                  {c.fx_implied != null && (
                    <Badge variant="info">FX ~{c.fx_implied.toFixed(4)}</Badge>
                  )}
                </div>
                <div className="mt-2 flex flex-col items-stretch gap-2 sm:flex-row sm:items-center">
                  <TxLeg
                    label="Out"
                    description={c.debit.description}
                    date={c.debit.booking_date}
                    amount={-c.debit.amount}
                    currency={c.debit.currency}
                  />
                  <ArrowRight className="mx-auto hidden h-4 w-4 shrink-0 text-muted-foreground sm:block" />
                  <TxLeg
                    label="In"
                    description={c.credit.description}
                    date={c.credit.booking_date}
                    amount={c.credit.amount}
                    currency={c.credit.currency}
                  />
                </div>
                <div className="mt-3 flex justify-end gap-2">
                  <Button variant="ghost" size="sm" onClick={() => reject(c)}>
                    <X className="h-4 w-4" /> Reject
                  </Button>
                  <Button size="sm" onClick={() => confirm(c)} loading={link.isPending}>
                    <Check className="h-4 w-4" /> Link transfer
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function TxLeg({
  label,
  description,
  date,
  amount,
  currency,
}: {
  label: string;
  description: string;
  date: string;
  amount: number;
  currency: string;
}) {
  return (
    <div className="flex-1 rounded-md bg-muted/50 p-2.5">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="truncate text-sm font-medium text-foreground">{description}</p>
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{formatDate(date)}</span>
        <span
          className={
            amount < 0
              ? 'text-sm font-semibold tabular-nums text-negative'
              : 'text-sm font-semibold tabular-nums text-positive'
          }
        >
          {formatMoney(amount, currency as Currency, { signDisplay: 'always' })}
        </span>
      </div>
    </div>
  );
}
