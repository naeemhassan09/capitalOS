import { useMemo, useState } from 'react';
import { Plus, Pencil, Trash2, PiggyBank, Check, X } from 'lucide-react';
import {
  useBudgetReport,
  useCreateBudget,
  useUpdateBudget,
  useDeleteBudget,
} from '@/api/budgets';
import { useDashboard } from '@/api/dashboard';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { num, formatMoney } from '@/utils/money';
import { PageHeader } from '@/components/PageHeader';
import { CategorySelect } from '@/components/CategorySelect';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { Progress } from '@/components/ui/Progress';
import { Dialog } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Field } from '@/components/ui/Label';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { SkeletonCards } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { EmptyState } from '@/components/ui/EmptyState';
import type { BudgetReportRow, Currency } from '@/types';

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

function recentYears(count = 6): number[] {
  const now = new Date().getFullYear();
  return Array.from({ length: count }, (_, i) => now - i);
}

// Progress-bar tint keyed off percent used: green under 80, amber 80–100, red over.
function usageIndicator(pct: number): string {
  if (pct > 100) return 'bg-negative';
  if (pct >= 80) return 'bg-warning';
  return 'bg-positive';
}

export function BudgetPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [formOpen, setFormOpen] = useState(false);
  const [deleting, setDeleting] = useState<BudgetReportRow | null>(null);

  const dashboard = useDashboard();
  const report = useBudgetReport(year, month);
  const base = (report.data?.base_currency ?? dashboard.data?.base_currency ?? 'EUR') as Currency;

  const rows = useMemo(
    () => (report.data?.rows ?? []).slice().sort((a, b) => num(b.actual_base) - num(a.actual_base)),
    [report.data],
  );
  const usedCategoryIds = useMemo(() => new Set(rows.map((r) => r.category_id)), [rows]);

  const totalBudget = num(report.data?.total_budget_base);
  const totalActual = num(report.data?.total_actual_base);
  const overallPct = totalBudget > 0 ? (totalActual / totalBudget) * 100 : 0;

  const years = recentYears();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Budget"
        description="Set monthly limits per category and track spend against them. Actuals are in your base currency."
        actions={
          <Button size="sm" onClick={() => setFormOpen(true)}>
            <Plus className="h-4 w-4" /> Add budget
          </Button>
        }
      />

      <Card>
        <CardContent className="pt-4">
          <div className="grid grid-cols-2 gap-3 sm:max-w-md">
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
          </div>
        </CardContent>
      </Card>

      {report.isLoading ? (
        <SkeletonCards count={3} />
      ) : report.isError ? (
        <ErrorState error={report.error} onRetry={() => report.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<PiggyBank className="h-10 w-10" />}
          title="No budgets yet"
          description="Budgets are optional — add one to start tracking a category."
          action={
            <Button onClick={() => setFormOpen(true)}>
              <Plus className="h-4 w-4" /> Add budget
            </Button>
          }
        />
      ) : (
        <>
          <BudgetSummary
            totalBudget={totalBudget}
            totalActual={totalActual}
            overallPct={overallPct}
            base={base}
          />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {rows.map((row) => (
              <BudgetCard key={row.id} row={row} base={base} onDelete={() => setDeleting(row)} />
            ))}
          </div>
        </>
      )}

      <AddBudgetDialog
        open={formOpen}
        onClose={() => setFormOpen(false)}
        usedCategoryIds={usedCategoryIds}
      />
      <DeleteBudgetDialog row={deleting} onClose={() => setDeleting(null)} />
    </div>
  );
}

function BudgetSummary({
  totalBudget,
  totalActual,
  overallPct,
  base,
}: {
  totalBudget: number;
  totalActual: number;
  overallPct: number;
  base: Currency;
}) {
  const remaining = totalBudget - totalActual;
  return (
    <Card>
      <CardContent className="pt-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SummaryStat label="Total budget" value={formatMoney(totalBudget, base)} />
          <SummaryStat label="Total actual" value={formatMoney(totalActual, base)} />
          <SummaryStat
            label="Remaining"
            value={formatMoney(remaining, base)}
            className={remaining < 0 ? 'text-negative' : 'text-foreground'}
          />
          <SummaryStat label="Overall used" value={`${Math.round(overallPct)}%`} />
        </div>
        <div className="mt-4">
          <Progress
            value={overallPct}
            indicatorClassName={usageIndicator(overallPct)}
            label="Overall budget used"
          />
        </div>
      </CardContent>
    </Card>
  );
}

function SummaryStat({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className="rounded-lg border border-border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`mt-1 text-lg font-semibold tabular-nums ${className ?? 'text-foreground'}`}>
        {value}
      </p>
    </div>
  );
}

function BudgetCard({
  row,
  base,
  onDelete,
}: {
  row: BudgetReportRow;
  base: Currency;
  onDelete: () => void;
}) {
  const limit = num(row.amount);
  const actual = num(row.actual_base);
  const remaining = num(row.remaining_base);
  const pct = num(row.percent_used);
  const prev = num(row.prev_month_base);
  const avg = num(row.avg_3m_base);
  const overBudget = remaining < 0;

  return (
    <Card>
      <CardContent className="pt-4">
        <div className="flex items-start justify-between gap-2">
          <p className="min-w-0 truncate font-medium text-foreground">{row.category_name}</p>
          <span className="shrink-0 text-sm font-semibold tabular-nums text-muted-foreground">
            {Math.round(pct)}%
          </span>
        </div>

        <div className="mt-3">
          <Progress
            value={pct}
            indicatorClassName={usageIndicator(pct)}
            label={`${row.category_name} budget used`}
          />
          <div className="mt-1.5 flex items-center justify-between text-sm">
            <span className="font-medium text-foreground tabular-nums">
              {formatMoney(actual, base)}
            </span>
            <EditableLimit row={row} base={base} />
          </div>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
          <div className="rounded-md bg-muted/50 p-2.5">
            <p className="text-xs text-muted-foreground">Remaining</p>
            <p
              className={`font-semibold tabular-nums ${overBudget ? 'text-negative' : 'text-foreground'}`}
            >
              {formatMoney(remaining, base)}
            </p>
          </div>
          <div className="rounded-md bg-muted/50 p-2.5">
            <p className="text-xs text-muted-foreground">Prev month</p>
            <p className="font-semibold tabular-nums text-foreground">{formatMoney(prev, base)}</p>
          </div>
          <div className="rounded-md bg-muted/50 p-2.5">
            <p className="text-xs text-muted-foreground">3-mo avg</p>
            <p className="font-semibold tabular-nums text-foreground">{formatMoney(avg, base)}</p>
          </div>
        </div>

        <div className="mt-4 flex justify-end">
          <Button variant="ghost" size="sm" className="text-danger" onClick={onDelete}>
            <Trash2 className="h-3.5 w-3.5" /> Delete
          </Button>
        </div>

        <p className="sr-only">Monthly limit {formatMoney(limit, base)}</p>
      </CardContent>
    </Card>
  );
}

// Inline edit of a budget's monthly limit.
function EditableLimit({ row, base }: { row: BudgetReportRow; base: Currency }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(String(num(row.amount)));
  const update = useUpdateBudget();
  const toast = useToast();
  const limit = num(row.amount);

  const save = async () => {
    const amount = Number(value);
    if (!Number.isFinite(amount) || amount < 0) {
      toast.error('Enter a valid limit');
      return;
    }
    try {
      await update.mutateAsync({ id: row.id, amount });
      toast.success('Budget updated');
      setEditing(false);
    } catch (err) {
      toast.error('Update failed', err instanceof ApiError ? err.message : undefined);
    }
  };

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => {
          setValue(String(limit));
          setEditing(true);
        }}
        className="group inline-flex items-center gap-1 text-muted-foreground hover:text-foreground focus-ring rounded"
        aria-label="Edit monthly limit"
      >
        <span className="tabular-nums">of {formatMoney(limit, base)}</span>
        <Pencil className="h-3 w-3 opacity-60 group-hover:opacity-100" />
      </button>
    );
  }

  return (
    <div className="flex items-center gap-1">
      <Input
        type="number"
        step="0.01"
        min={0}
        value={value}
        autoFocus
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') save();
          if (e.key === 'Escape') setEditing(false);
        }}
        className="h-8 w-28 text-right"
        aria-label="Monthly limit"
      />
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-positive"
        onClick={save}
        loading={update.isPending}
        aria-label="Save limit"
      >
        <Check className="h-4 w-4" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        onClick={() => setEditing(false)}
        aria-label="Cancel"
      >
        <X className="h-4 w-4" />
      </Button>
    </div>
  );
}

function AddBudgetDialog({
  open,
  onClose,
  usedCategoryIds,
}: {
  open: boolean;
  onClose: () => void;
  usedCategoryIds: Set<string>;
}) {
  const create = useCreateBudget();
  const toast = useToast();
  const [categoryId, setCategoryId] = useState('');
  const [amount, setAmount] = useState('');
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setCategoryId('');
    setAmount('');
    setError(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const submit = async () => {
    if (!categoryId) {
      setError('Pick a category');
      return;
    }
    const value = Number(amount);
    if (!Number.isFinite(value) || value < 0) {
      setError('Enter a valid amount');
      return;
    }
    setError(null);
    try {
      await create.mutateAsync({ category_id: categoryId, amount: value });
      toast.success('Budget added');
      handleClose();
    } catch (err) {
      toast.error('Could not add budget', err instanceof ApiError ? err.message : undefined);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      title="Add budget"
      size="sm"
      footer={
        <>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button onClick={submit} loading={create.isPending}>
            Add budget
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Category" required error={error && !categoryId ? error : undefined}>
          <CategorySelect
            includeUncategorised={false}
            value={categoryId}
            invalid={!!error && !categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            // Categories that already have a budget are disabled (409 on the backend).
            disabledOptionIds={usedCategoryIds}
          />
        </Field>
        <Field
          label="Monthly limit"
          required
          error={error && categoryId ? error : undefined}
        >
          <Input
            type="number"
            step="0.01"
            min={0}
            value={amount}
            invalid={!!error && !!categoryId}
            onChange={(e) => setAmount(e.target.value)}
          />
        </Field>
      </div>
    </Dialog>
  );
}

function DeleteBudgetDialog({
  row,
  onClose,
}: {
  row: BudgetReportRow | null;
  onClose: () => void;
}) {
  const del = useDeleteBudget();
  const toast = useToast();
  return (
    <ConfirmDialog
      open={!!row}
      onClose={onClose}
      title="Delete budget?"
      description={row ? `The budget for "${row.category_name}" will be removed.` : ''}
      confirmLabel="Delete"
      confirmVariant="destructive"
      loading={del.isPending}
      onConfirm={async () => {
        if (!row) return;
        try {
          await del.mutateAsync(row.id);
          toast.success('Budget deleted');
          onClose();
        } catch (err) {
          toast.error('Delete failed', err instanceof ApiError ? err.message : undefined);
        }
      }}
    />
  );
}
