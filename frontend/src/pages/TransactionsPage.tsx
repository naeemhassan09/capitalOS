import { useMemo, useState } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
  type RowSelectionState,
} from '@tanstack/react-table';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Search,
  ChevronLeft,
  ChevronRight,
  Tags,
  CheckCheck,
  ArrowLeftRight,
  Plus,
  X,
  Pencil,
  Trash2,
} from 'lucide-react';
import {
  useTransactions,
  useCreateTransaction,
  useCreateTransfer,
  useUpdateTransaction,
  useDeleteTransaction,
  useBulkCategorise,
  useBulkReview,
} from '@/api/transactions';
import { useAccounts } from '@/api/accounts';
import { useFlatCategories } from '@/api/categories';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { formatMoney } from '@/utils/money';
import { formatDate } from '@/utils/date';
import { TX_KIND_LABELS, TX_STATUS_LABELS, COUNTRY_LABELS } from '@/utils/labels';
import { PageHeader } from '@/components/PageHeader';
import { CategorySelect } from '@/components/CategorySelect';
import { TxStatusBadge } from '@/components/StatusBadge';
import { TransferMatchPanel } from '@/components/TransferMatchPanel';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { Field } from '@/components/ui/Label';
import { Badge } from '@/components/ui/Badge';
import { Drawer } from '@/components/ui/Drawer';
import { Dialog } from '@/components/ui/Dialog';
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
import { SkeletonTable } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import type {
  Account,
  Transaction,
  TransactionQuery,
  TxKind,
  TxStatus,
  Currency,
  Country,
} from '@/types';

const PAGE_SIZE = 25;
const columnHelper = createColumnHelper<Transaction>();

interface Filters {
  account_id: string;
  category_id: string;
  kind: string;
  status: string;
  search: string;
  date_from: string;
  date_to: string;
  is_reviewed: string;
}

const EMPTY_FILTERS: Filters = {
  account_id: '',
  category_id: '',
  kind: '',
  status: '',
  search: '',
  date_from: '',
  date_to: '',
  is_reviewed: '',
};

export function TransactionsPage() {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = useState(0);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [deleting, setDeleting] = useState<Transaction | null>(null);
  const [bulkCatOpen, setBulkCatOpen] = useState(false);
  const [showTransfers, setShowTransfers] = useState(false);
  const [adding, setAdding] = useState(false);

  const accounts = useAccounts();
  const { flat: categories } = useFlatCategories();
  const catName = useMemo(() => {
    const map = new Map(categories.map((c) => [c.id, c.label]));
    return (id: string | null) => (id ? map.get(id) ?? 'Category' : '—');
  }, [categories]);
  const acctName = useMemo(() => {
    const map = new Map((accounts.data ?? []).map((a) => [a.id, a.name]));
    return (id: string) => map.get(id) ?? '—';
  }, [accounts.data]);

  const query: TransactionQuery = useMemo(() => {
    const q: TransactionQuery = { limit: PAGE_SIZE, offset: page * PAGE_SIZE };
    if (filters.account_id) q.account_id = filters.account_id;
    if (filters.category_id) q.category_id = filters.category_id;
    if (filters.kind) q.kind = filters.kind as TxKind;
    if (filters.status) q.status = filters.status as TxStatus;
    if (filters.search) q.search = filters.search;
    if (filters.date_from) q.date_from = filters.date_from;
    if (filters.date_to) q.date_to = filters.date_to;
    if (filters.is_reviewed) q.is_reviewed = filters.is_reviewed === 'yes';
    return q;
  }, [filters, page]);

  const { data, isLoading, isError, error, refetch, isFetching } = useTransactions(query);
  const bulkCategorise = useBulkCategorise();
  const bulkReview = useBulkReview();
  const toast = useToast();

  const rows = data?.items ?? [];
  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const columns = useMemo(
    () => [
      columnHelper.display({
        id: 'select',
        header: ({ table }) => (
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-input text-primary focus-ring"
            checked={table.getIsAllRowsSelected()}
            ref={(el) => {
              if (el) el.indeterminate = table.getIsSomeRowsSelected() && !table.getIsAllRowsSelected();
            }}
            onChange={table.getToggleAllRowsSelectedHandler()}
            aria-label="Select all rows"
          />
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-input text-primary focus-ring"
            checked={row.getIsSelected()}
            onChange={row.getToggleSelectedHandler()}
            aria-label="Select row"
          />
        ),
      }),
      columnHelper.accessor('booking_date', {
        header: 'Date',
        cell: (info) => <span className="whitespace-nowrap">{formatDate(info.getValue())}</span>,
      }),
      columnHelper.accessor('description', {
        header: 'Description',
        cell: ({ row }) => (
          <div className="min-w-[180px]">
            <p className="truncate font-medium text-foreground">{row.original.description}</p>
            {row.original.merchant && (
              <p className="truncate text-xs text-muted-foreground">{row.original.merchant}</p>
            )}
          </div>
        ),
      }),
      columnHelper.accessor('account_id', {
        header: 'Account',
        cell: (info) => <span className="whitespace-nowrap text-sm">{acctName(info.getValue())}</span>,
      }),
      columnHelper.accessor('category_id', {
        header: 'Category',
        cell: (info) => <span className="text-sm">{catName(info.getValue())}</span>,
      }),
      columnHelper.accessor('status', {
        header: 'Status',
        cell: (info) => <TxStatusBadge status={info.getValue()} />,
      }),
      columnHelper.display({
        id: 'flags',
        header: '',
        cell: ({ row }) => (
          <div className="flex gap-1">
            {row.original.is_transfer && <Badge variant="info">Transfer</Badge>}
            {row.original.is_reviewed && <Badge variant="success">Reviewed</Badge>}
          </div>
        ),
      }),
      columnHelper.accessor('amount', {
        header: () => <div className="text-right">Amount</div>,
        cell: ({ row }) => {
          const signed = row.original.direction === 'debit' ? -row.original.amount : row.original.amount;
          return (
            <div
              className={
                signed < 0
                  ? 'text-right font-medium tabular-nums text-negative'
                  : 'text-right font-medium tabular-nums text-positive'
              }
            >
              {formatMoney(signed, row.original.currency as Currency, { signDisplay: 'always' })}
            </div>
          );
        },
      }),
      columnHelper.display({
        id: 'actions',
        header: '',
        cell: ({ row }) => (
          <div className="flex justify-end gap-1">
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditing(row.original)} aria-label="Edit">
              <Pencil className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-danger"
              onClick={() => setDeleting(row.original)}
              aria-label="Delete"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ),
      }),
    ],
    [acctName, catName],
  );

  const table = useReactTable({
    data: rows,
    columns,
    state: { rowSelection },
    getRowId: (row) => row.id,
    enableRowSelection: true,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount,
  });

  const selectedIds = Object.keys(rowSelection).filter((id) => rowSelection[id]);
  const clearSelection = () => setRowSelection({});

  const updateFilter = (patch: Partial<Filters>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(0);
  };

  const runBulkReview = async () => {
    try {
      await bulkReview.mutateAsync({ ids: selectedIds, is_reviewed: true });
      toast.success(`${selectedIds.length} marked reviewed`);
      clearSelection();
    } catch (err) {
      toast.error('Bulk review failed', err instanceof ApiError ? err.message : undefined);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Transactions"
        description="Filter, review and categorise. Amounts show signed direction."
        actions={
          <>
            <Button variant={showTransfers ? 'primary' : 'outline'} size="sm" onClick={() => setShowTransfers((v) => !v)}>
              <ArrowLeftRight className="h-4 w-4" /> Match transfers
            </Button>
            <Button variant="primary" size="sm" onClick={() => setAdding(true)}>
              <Plus className="h-4 w-4" /> Add transaction
            </Button>
          </>
        }
      />

      {showTransfers && <TransferMatchPanel onClose={() => setShowTransfers(false)} />}

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="relative sm:col-span-2">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search description or merchant"
                className="pl-9"
                value={filters.search}
                onChange={(e) => updateFilter({ search: e.target.value })}
              />
            </div>
            <Select value={filters.account_id} onChange={(e) => updateFilter({ account_id: e.target.value })}>
              <option value="">All accounts</option>
              {(accounts.data ?? []).map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </Select>
            <CategorySelect
              includeUncategorised={false}
              value={filters.category_id}
              onChange={(e) => updateFilter({ category_id: e.target.value })}
            >
              <option value="">All categories</option>
            </CategorySelect>
            <Select value={filters.kind} onChange={(e) => updateFilter({ kind: e.target.value })}>
              <option value="">All kinds</option>
              {(Object.keys(TX_KIND_LABELS) as TxKind[]).map((k) => (
                <option key={k} value={k}>
                  {TX_KIND_LABELS[k]}
                </option>
              ))}
            </Select>
            <Select value={filters.status} onChange={(e) => updateFilter({ status: e.target.value })}>
              <option value="">All statuses</option>
              {(Object.keys(TX_STATUS_LABELS) as TxStatus[]).map((s) => (
                <option key={s} value={s}>
                  {TX_STATUS_LABELS[s]}
                </option>
              ))}
            </Select>
            <Select value={filters.is_reviewed} onChange={(e) => updateFilter({ is_reviewed: e.target.value })}>
              <option value="">Any review state</option>
              <option value="yes">Reviewed</option>
              <option value="no">Unreviewed</option>
            </Select>
            <Input type="date" aria-label="From date" value={filters.date_from} onChange={(e) => updateFilter({ date_from: e.target.value })} />
            <Input type="date" aria-label="To date" value={filters.date_to} onChange={(e) => updateFilter({ date_to: e.target.value })} />
          </div>
          <div className="mt-3 flex justify-end">
            <Button variant="ghost" size="sm" onClick={() => { setFilters(EMPTY_FILTERS); setPage(0); }}>
              Clear filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Bulk action bar */}
      {selectedIds.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 p-3">
          <span className="text-sm font-medium text-foreground">{selectedIds.length} selected</span>
          <div className="flex-1" />
          <Button size="sm" variant="outline" onClick={() => setBulkCatOpen(true)}>
            <Tags className="h-4 w-4" /> Categorise
          </Button>
          <Button size="sm" variant="outline" onClick={runBulkReview} loading={bulkReview.isPending}>
            <CheckCheck className="h-4 w-4" /> Mark reviewed
          </Button>
          <Button size="sm" variant="ghost" onClick={clearSelection}>
            <X className="h-4 w-4" /> Clear
          </Button>
        </div>
      )}

      {/* Table */}
      {isLoading ? (
        <Card>
          <CardContent className="pt-4">
            <SkeletonTable rows={8} cols={7} />
          </CardContent>
        </Card>
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : (
        <>
          <TableContainer>
            <Table>
              <TableHeader>
                {table.getHeaderGroups().map((hg) => (
                  <TableRow key={hg.id}>
                    {hg.headers.map((header) => (
                      <TableHead key={header.id}>
                        {flexRender(header.column.columnDef.header, header.getContext())}
                      </TableHead>
                    ))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {rows.length === 0 ? (
                  <TableEmpty colSpan={columns.length}>No transactions match your filters.</TableEmpty>
                ) : (
                  table.getRowModel().rows.map((row) => (
                    <TableRow key={row.id} data-selected={row.getIsSelected()}>
                      {row.getVisibleCells().map((cell) => (
                        <TableCell key={cell.id}>
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>

          {/* Pagination */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              {total === 0 ? '0' : `${page * PAGE_SIZE + 1}–${Math.min((page + 1) * PAGE_SIZE, total)}`} of {total}
              {isFetching && <span className="ml-2 text-xs">Updating…</span>}
            </p>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}>
                <ChevronLeft className="h-4 w-4" /> Prev
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page + 1} / {pageCount}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                disabled={page >= pageCount - 1}
              >
                Next <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </>
      )}

      <AddTransactionDrawer open={adding} onClose={() => setAdding(false)} />
      <EditTransactionDrawer transaction={editing} onClose={() => setEditing(null)} />
      <DeleteTransactionDialog transaction={deleting} onClose={() => setDeleting(null)} />
      <BulkCategoriseDialog
        open={bulkCatOpen}
        onClose={() => setBulkCatOpen(false)}
        onApply={async (categoryId, markReviewed) => {
          try {
            await bulkCategorise.mutateAsync({
              ids: selectedIds,
              category_id: categoryId || null,
              mark_reviewed: markReviewed,
            });
            toast.success(`${selectedIds.length} categorised`);
            setBulkCatOpen(false);
            clearSelection();
          } catch (err) {
            toast.error('Bulk categorise failed', err instanceof ApiError ? err.message : undefined);
          }
        }}
        loading={bulkCategorise.isPending}
      />
    </div>
  );
}

// ------- Add transaction (manual) -------

type AddMode = 'expense' | 'income' | 'transfer';

const todayISO = () => new Date().toISOString().slice(0, 10);

/** <option>s for the user's non-archived accounts, grouped by country. */
function AccountOptions({ accounts }: { accounts: Account[] }) {
  const active = accounts.filter((a) => !a.is_archived);
  const byCountry = new Map<Country, Account[]>();
  for (const a of active) {
    const list = byCountry.get(a.country) ?? [];
    list.push(a);
    byCountry.set(a.country, list);
  }
  return (
    <>
      {Array.from(byCountry.entries()).map(([country, list]) => (
        <optgroup key={country} label={COUNTRY_LABELS[country]}>
          {list.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} ({a.currency})
            </option>
          ))}
        </optgroup>
      ))}
    </>
  );
}

const entrySchema = z.object({
  account_id: z.string().min(1, 'Select an account'),
  amount: z.coerce.number().positive('Enter an amount greater than 0'),
  booking_date: z.string().min(1, 'Required'),
  category_id: z.string().optional(),
  merchant: z.string().optional(),
  description: z.string().optional(),
  notes: z.string().optional(),
});
type EntryValues = z.infer<typeof entrySchema>;

const transferSchema = z
  .object({
    from_account_id: z.string().min(1, 'Select an account'),
    to_account_id: z.string().min(1, 'Select an account'),
    amount: z.coerce.number().positive('Enter an amount greater than 0'),
    booking_date: z.string().min(1, 'Required'),
    description: z.string().optional(),
    category_id: z.string().optional(),
  })
  .refine((v) => v.from_account_id !== v.to_account_id, {
    message: 'Choose two different accounts',
    path: ['to_account_id'],
  });
type TransferValues = z.infer<typeof transferSchema>;

const MODE_TABS: { value: AddMode; label: string }[] = [
  { value: 'expense', label: 'Expense' },
  { value: 'income', label: 'Income' },
  { value: 'transfer', label: 'Transfer' },
];

function AddTransactionDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [mode, setMode] = useState<AddMode>('expense');
  const accounts = useAccounts();
  const activeAccounts = useMemo(
    () => (accounts.data ?? []).filter((a) => !a.is_archived),
    [accounts.data],
  );
  const currencyOf = useMemo(() => {
    const map = new Map(activeAccounts.map((a) => [a.id, a.currency]));
    return (id: string): Currency => map.get(id) ?? 'EUR';
  }, [activeAccounts]);

  const createTx = useCreateTransaction();
  const createTransfer = useCreateTransfer();
  const toast = useToast();

  const entryForm = useForm<EntryValues>({
    resolver: zodResolver(entrySchema),
    defaultValues: {
      account_id: '',
      amount: undefined,
      booking_date: todayISO(),
      category_id: '',
      merchant: '',
      description: '',
      notes: '',
    },
  });

  const transferForm = useForm<TransferValues>({
    resolver: zodResolver(transferSchema),
    defaultValues: {
      from_account_id: '',
      to_account_id: '',
      amount: undefined,
      booking_date: todayISO(),
      description: '',
      category_id: '',
    },
  });

  const resetAll = () => {
    entryForm.reset({
      account_id: '',
      amount: undefined,
      booking_date: todayISO(),
      category_id: '',
      merchant: '',
      description: '',
      notes: '',
    });
    transferForm.reset({
      from_account_id: '',
      to_account_id: '',
      amount: undefined,
      booking_date: todayISO(),
      description: '',
      category_id: '',
    });
  };

  const close = () => {
    resetAll();
    setMode('expense');
    onClose();
  };

  const submitEntry = entryForm.handleSubmit(async (values) => {
    const kind = mode === 'income' ? 'income' : 'expense';
    const direction = mode === 'income' ? 'credit' : 'debit';
    try {
      await createTx.mutateAsync({
        account_id: values.account_id,
        booking_date: values.booking_date,
        description: values.description?.trim() || (kind === 'income' ? 'Income' : 'Expense'),
        merchant: mode === 'expense' ? values.merchant?.trim() || null : null,
        amount: String(values.amount),
        currency: currencyOf(values.account_id),
        direction,
        kind,
        category_id: values.category_id || null,
        notes: mode === 'expense' ? values.notes?.trim() || null : null,
      });
      toast.success(kind === 'income' ? 'Income added' : 'Expense added');
      close();
    } catch (err) {
      toast.error('Could not add transaction', err instanceof ApiError ? err.message : undefined);
    }
  });

  const submitTransfer = transferForm.handleSubmit(async (values) => {
    try {
      await createTransfer.mutateAsync({
        from_account_id: values.from_account_id,
        to_account_id: values.to_account_id,
        amount: String(values.amount),
        booking_date: values.booking_date,
        description: values.description?.trim() || null,
        category_id: values.category_id || null,
      });
      toast.success('Transfer recorded');
      close();
    } catch (err) {
      toast.error('Could not record transfer', err instanceof ApiError ? err.message : undefined);
    }
  });

  const isTransfer = mode === 'transfer';
  const onSubmit = isTransfer ? submitTransfer : submitEntry;
  const pending = createTx.isPending || createTransfer.isPending;

  const transferValues = transferForm.watch();
  const sameAccount =
    isTransfer &&
    !!transferValues.from_account_id &&
    transferValues.from_account_id === transferValues.to_account_id;

  const entryErrors = entryForm.formState.errors;
  const transferErrors = transferForm.formState.errors;

  return (
    <Drawer
      open={open}
      onClose={close}
      title="Add transaction"
      description="Record a manual expense, income, or transfer between accounts."
      footer={
        <>
          <Button variant="outline" onClick={close}>
            Cancel
          </Button>
          <Button onClick={onSubmit} loading={pending} disabled={sameAccount}>
            {isTransfer ? 'Record transfer' : mode === 'income' ? 'Add income' : 'Add expense'}
          </Button>
        </>
      }
    >
      {/* Segmented control */}
      <div className="mb-5 grid grid-cols-3 gap-1 rounded-lg border border-border bg-muted/40 p-1">
        {MODE_TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => setMode(t.value)}
            aria-pressed={mode === t.value}
            className={
              mode === t.value
                ? 'rounded-md bg-card px-3 py-1.5 text-sm font-medium text-foreground shadow-sm focus-ring'
                : 'rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground hover:text-foreground focus-ring'
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      {isTransfer ? (
        <form onSubmit={submitTransfer} className="space-y-4">
          <Field label="From account" required error={transferErrors.from_account_id?.message}>
            <Select invalid={!!transferErrors.from_account_id} {...transferForm.register('from_account_id')}>
              <option value="">Select account…</option>
              <AccountOptions accounts={activeAccounts} />
            </Select>
          </Field>
          <Field
            label="To account"
            required
            error={transferErrors.to_account_id?.message}
          >
            <Select invalid={!!transferErrors.to_account_id} {...transferForm.register('to_account_id')}>
              <option value="">Select account…</option>
              <AccountOptions accounts={activeAccounts} />
            </Select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Amount" required error={transferErrors.amount?.message}>
              <Input
                type="number"
                step="0.01"
                min="0"
                placeholder="0.00"
                invalid={!!transferErrors.amount}
                {...transferForm.register('amount')}
              />
            </Field>
            <Field label="Date" required error={transferErrors.booking_date?.message}>
              <Input type="date" {...transferForm.register('booking_date')} />
            </Field>
          </div>
          <Field label="Description">
            <Input placeholder="e.g. Move to savings" {...transferForm.register('description')} />
          </Field>
        </form>
      ) : (
        <form onSubmit={submitEntry} className="space-y-4">
          <Field label="Account" required error={entryErrors.account_id?.message}>
            <Select invalid={!!entryErrors.account_id} {...entryForm.register('account_id')}>
              <option value="">Select account…</option>
              <AccountOptions accounts={activeAccounts} />
            </Select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Amount" required error={entryErrors.amount?.message}>
              <Input
                type="number"
                step="0.01"
                min="0"
                placeholder="0.00"
                invalid={!!entryErrors.amount}
                {...entryForm.register('amount')}
              />
            </Field>
            <Field label="Date" required error={entryErrors.booking_date?.message}>
              <Input type="date" {...entryForm.register('booking_date')} />
            </Field>
          </div>
          <Field label="Category">
            <CategorySelect {...entryForm.register('category_id')} />
          </Field>
          {mode === 'expense' && (
            <Field label="Merchant">
              <Input placeholder="Optional" {...entryForm.register('merchant')} />
            </Field>
          )}
          <Field label="Description">
            <Input placeholder="Optional" {...entryForm.register('description')} />
          </Field>
          {mode === 'expense' && (
            <Field label="Notes">
              <Textarea rows={3} {...entryForm.register('notes')} />
            </Field>
          )}
        </form>
      )}
    </Drawer>
  );
}

const editSchema = z.object({
  description: z.string().min(1, 'Required'),
  merchant: z.string().optional(),
  booking_date: z.string().min(1, 'Required'),
  amount: z.coerce.number().nonnegative('Use a positive magnitude'),
  direction: z.enum(['credit', 'debit']),
  kind: z.enum(['expense', 'income', 'transfer', 'adjustment', 'fee', 'refund', 'other']),
  status: z.enum(['settled', 'pending', 'projected']),
  category_id: z.string().optional(),
  notes: z.string().optional(),
});
type EditValues = z.infer<typeof editSchema>;

function EditTransactionDrawer({ transaction, onClose }: { transaction: Transaction | null; onClose: () => void }) {
  const update = useUpdateTransaction();
  const toast = useToast();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    values: {
      description: transaction?.description ?? '',
      merchant: transaction?.merchant ?? '',
      booking_date: transaction?.booking_date ?? '',
      amount: transaction?.amount ?? 0,
      direction: transaction?.direction ?? 'debit',
      kind: transaction?.kind ?? 'expense',
      status: transaction?.status ?? 'settled',
      category_id: transaction?.category_id ?? '',
      notes: transaction?.notes ?? '',
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    if (!transaction) return;
    try {
      await update.mutateAsync({
        id: transaction.id,
        ...values,
        merchant: values.merchant || null,
        category_id: values.category_id || null,
        notes: values.notes || null,
      });
      toast.success('Transaction updated');
      onClose();
    } catch (err) {
      toast.error('Update failed', err instanceof ApiError ? err.message : undefined);
    }
  });

  return (
    <Drawer
      open={!!transaction}
      onClose={onClose}
      title="Edit transaction"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={onSubmit} loading={update.isPending}>
            Save
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Description" required error={errors.description?.message}>
          <Input invalid={!!errors.description} {...register('description')} />
        </Field>
        <Field label="Merchant">
          <Input {...register('merchant')} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Date" required error={errors.booking_date?.message}>
            <Input type="date" {...register('booking_date')} />
          </Field>
          <Field label="Amount (magnitude)" required error={errors.amount?.message}>
            <Input type="number" step="0.01" {...register('amount')} />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Direction">
            <Select {...register('direction')}>
              <option value="debit">Debit (out)</option>
              <option value="credit">Credit (in)</option>
            </Select>
          </Field>
          <Field label="Kind">
            <Select {...register('kind')}>
              {(Object.keys(TX_KIND_LABELS) as TxKind[]).map((k) => (
                <option key={k} value={k}>
                  {TX_KIND_LABELS[k]}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Status">
            <Select {...register('status')}>
              {(Object.keys(TX_STATUS_LABELS) as TxStatus[]).map((s) => (
                <option key={s} value={s}>
                  {TX_STATUS_LABELS[s]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Category">
            <CategorySelect {...register('category_id')} />
          </Field>
        </div>
        <Field label="Notes">
          <Textarea rows={3} {...register('notes')} />
        </Field>
      </form>
    </Drawer>
  );
}

function DeleteTransactionDialog({ transaction, onClose }: { transaction: Transaction | null; onClose: () => void }) {
  const del = useDeleteTransaction();
  const toast = useToast();
  return (
    <ConfirmDialog
      open={!!transaction}
      onClose={onClose}
      title="Delete transaction?"
      description={transaction ? `"${transaction.description}" will be permanently removed.` : ''}
      confirmLabel="Delete"
      confirmVariant="destructive"
      loading={del.isPending}
      onConfirm={async () => {
        if (!transaction) return;
        try {
          await del.mutateAsync(transaction.id);
          toast.success('Transaction deleted');
          onClose();
        } catch (err) {
          toast.error('Delete failed', err instanceof ApiError ? err.message : undefined);
        }
      }}
    />
  );
}

function BulkCategoriseDialog({
  open,
  onClose,
  onApply,
  loading,
}: {
  open: boolean;
  onClose: () => void;
  onApply: (categoryId: string, markReviewed: boolean) => void;
  loading: boolean;
}) {
  const [categoryId, setCategoryId] = useState('');
  const [markReviewed, setMarkReviewed] = useState(true);
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Categorise selected"
      size="sm"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => onApply(categoryId, markReviewed)} loading={loading}>
            Apply
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Category">
          <CategorySelect value={categoryId} onChange={(e) => setCategoryId(e.target.value)} />
        </Field>
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-input text-primary focus-ring"
            checked={markReviewed}
            onChange={(e) => setMarkReviewed(e.target.checked)}
          />
          Also mark as reviewed
        </label>
      </div>
    </Dialog>
  );
}
