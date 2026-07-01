import { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Plus, Pencil, Archive, ArchiveRestore, SlidersHorizontal, Wallet } from 'lucide-react';
import {
  useAccounts,
  useCreateAccount,
  useUpdateAccount,
  useAdjustBalance,
} from '@/api/accounts';
import { useInstitutions } from '@/api/institutions';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { formatMoney } from '@/utils/money';
import { SUPPORTED_CURRENCIES } from '@/utils/money';
import { todayISO } from '@/utils/date';
import {
  ACCOUNT_TYPE_LABELS,
  COUNTRY_LABELS,
  COUNTRY_FLAGS,
  LIABILITY_TYPES,
} from '@/utils/labels';
import { PageHeader } from '@/components/PageHeader';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { Field } from '@/components/ui/Label';
import { SkeletonCards } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { EmptyState } from '@/components/ui/EmptyState';
import type { Account, AccountCreate, AccountType, Country, Currency } from '@/types';

const ACCOUNT_TYPES = Object.keys(ACCOUNT_TYPE_LABELS) as AccountType[];
const COUNTRIES: Country[] = ['IE', 'PK', 'OTHER'];

const accountSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  account_type: z.enum([
    'current',
    'savings',
    'credit_card',
    'cash',
    'investment',
    'pension',
    'property',
    'loan',
    'receivable',
    'other_asset',
    'other_liability',
  ]),
  currency: z.enum(['EUR', 'PKR', 'USD', 'GBP', 'SAR']),
  country: z.enum(['IE', 'PK', 'OTHER']),
  current_balance: z.coerce.number(),
  credit_limit: z.coerce.number().optional(),
  institution_id: z.string().optional(),
  include_in_net_worth: z.boolean(),
  include_in_liquid_assets: z.boolean(),
  is_protected_reserve: z.boolean(),
  notes: z.string().optional(),
});

type AccountFormValues = z.infer<typeof accountSchema>;

export function AccountsPage() {
  const accounts = useAccounts();
  const institutions = useInstitutions();
  const [showArchived, setShowArchived] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const [adjusting, setAdjusting] = useState<Account | null>(null);

  const grouped = useMemo(() => {
    const list = (accounts.data ?? []).filter((a) => (showArchived ? true : !a.is_archived));
    const byCountry = new Map<Country, Map<AccountType, Account[]>>();
    for (const acc of list) {
      if (!byCountry.has(acc.country)) byCountry.set(acc.country, new Map());
      const byType = byCountry.get(acc.country)!;
      if (!byType.has(acc.account_type)) byType.set(acc.account_type, []);
      byType.get(acc.account_type)!.push(acc);
    }
    return byCountry;
  }, [accounts.data, showArchived]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Accounts"
        description="Balances are signed — liabilities are negative. Group by country, then account type."
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => setShowArchived((v) => !v)}>
              {showArchived ? 'Hide archived' : 'Show archived'}
            </Button>
            <Button
              size="sm"
              onClick={() => {
                setEditing(null);
                setFormOpen(true);
              }}
            >
              <Plus className="h-4 w-4" /> New account
            </Button>
          </>
        }
      />

      {accounts.isLoading ? (
        <SkeletonCards count={6} />
      ) : accounts.isError ? (
        <ErrorState error={accounts.error} onRetry={() => accounts.refetch()} />
      ) : grouped.size === 0 ? (
        <EmptyState
          icon={<Wallet className="h-10 w-10" />}
          title="No accounts yet"
          description="Add your bank, cash, credit-card and investment accounts to start tracking."
          action={
            <Button
              onClick={() => {
                setEditing(null);
                setFormOpen(true);
              }}
            >
              <Plus className="h-4 w-4" /> New account
            </Button>
          }
        />
      ) : (
        <div className="space-y-8">
          {COUNTRIES.filter((c) => grouped.has(c)).map((country) => {
            const byType = grouped.get(country)!;
            return (
              <section key={country}>
                <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-foreground">
                  <span>{COUNTRY_FLAGS[country]}</span> {COUNTRY_LABELS[country]}
                </h2>
                <div className="space-y-5">
                  {ACCOUNT_TYPES.filter((t) => byType.has(t)).map((type) => (
                    <div key={type}>
                      <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                        {ACCOUNT_TYPE_LABELS[type]}
                      </h3>
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {byType.get(type)!.map((acc) => (
                          <AccountCard
                            key={acc.id}
                            account={acc}
                            onEdit={() => {
                              setEditing(acc);
                              setFormOpen(true);
                            }}
                            onAdjust={() => setAdjusting(acc)}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}

      <AccountFormDialog
        open={formOpen}
        onClose={() => setFormOpen(false)}
        account={editing}
        institutions={institutions.data ?? []}
      />
      <AdjustBalanceDialog account={adjusting} onClose={() => setAdjusting(null)} />
    </div>
  );
}

function AccountCard({
  account,
  onEdit,
  onAdjust,
}: {
  account: Account;
  onEdit: () => void;
  onAdjust: () => void;
}) {
  const update = useUpdateAccount();
  const toast = useToast();
  const negative = account.current_balance < 0;

  const toggleArchive = async () => {
    try {
      await update.mutateAsync({ id: account.id, is_archived: !account.is_archived });
      toast.success(account.is_archived ? 'Account restored' : 'Account archived');
    } catch (err) {
      toast.error('Update failed', err instanceof ApiError ? err.message : undefined);
    }
  };

  return (
    <Card className={account.is_archived ? 'opacity-60' : undefined}>
      <CardContent className="pt-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate font-medium text-foreground">{account.name}</p>
            <p className="text-xs text-muted-foreground">
              {ACCOUNT_TYPE_LABELS[account.account_type]} · {account.currency}
            </p>
          </div>
          <div className="flex flex-wrap gap-1">
            {account.is_protected_reserve && <Badge variant="protected">Reserve</Badge>}
            {LIABILITY_TYPES.has(account.account_type) && <Badge variant="danger">Liability</Badge>}
            {account.is_archived && <Badge variant="secondary">Archived</Badge>}
          </div>
        </div>

        <p
          className={
            negative
              ? 'mt-3 text-2xl font-semibold tabular-nums text-negative'
              : 'mt-3 text-2xl font-semibold tabular-nums text-foreground'
          }
        >
          {formatMoney(account.current_balance, account.currency)}
        </p>
        {account.credit_limit != null && (
          <p className="text-xs text-muted-foreground">
            Limit {formatMoney(account.credit_limit, account.currency)}
          </p>
        )}

        <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
          {!account.include_in_net_worth && <span>Excluded from net worth</span>}
          {account.include_in_liquid_assets && <span>Liquid</span>}
        </div>

        <div className="mt-4 flex gap-2">
          <Button variant="outline" size="sm" onClick={onEdit}>
            <Pencil className="h-3.5 w-3.5" /> Edit
          </Button>
          <Button variant="outline" size="sm" onClick={onAdjust}>
            <SlidersHorizontal className="h-3.5 w-3.5" /> Adjust
          </Button>
          <Button variant="ghost" size="sm" onClick={toggleArchive} loading={update.isPending}>
            {account.is_archived ? (
              <ArchiveRestore className="h-3.5 w-3.5" />
            ) : (
              <Archive className="h-3.5 w-3.5" />
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function AccountFormDialog({
  open,
  onClose,
  account,
  institutions,
}: {
  open: boolean;
  onClose: () => void;
  account: Account | null;
  institutions: { id: string; name: string }[];
}) {
  const create = useCreateAccount();
  const update = useUpdateAccount();
  const toast = useToast();
  const isEdit = !!account;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AccountFormValues>({
    resolver: zodResolver(accountSchema),
    values: {
      name: account?.name ?? '',
      account_type: account?.account_type ?? 'current',
      currency: (account?.currency ?? 'EUR') as Currency,
      country: account?.country ?? 'IE',
      current_balance: account?.current_balance ?? 0,
      credit_limit: account?.credit_limit ?? undefined,
      institution_id: account?.institution_id ?? '',
      include_in_net_worth: account?.include_in_net_worth ?? true,
      include_in_liquid_assets: account?.include_in_liquid_assets ?? true,
      is_protected_reserve: account?.is_protected_reserve ?? false,
      notes: account?.notes ?? '',
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    const payload = {
      ...values,
      institution_id: values.institution_id || null,
      credit_limit: values.credit_limit ?? null,
    };
    try {
      if (isEdit && account) {
        await update.mutateAsync({ id: account.id, ...payload });
        toast.success('Account updated');
      } else {
        await create.mutateAsync(payload as AccountCreate);
        toast.success('Account created');
      }
      reset();
      onClose();
    } catch (err) {
      toast.error('Save failed', err instanceof ApiError ? err.message : undefined);
    }
  });

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={isEdit ? 'Edit account' : 'New account'}
      size="lg"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={onSubmit} loading={create.isPending || update.isPending}>
            {isEdit ? 'Save changes' : 'Create account'}
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Name" required error={errors.name?.message}>
          <Input invalid={!!errors.name} {...register('name')} />
        </Field>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="Type" required>
            <Select {...register('account_type')}>
              {ACCOUNT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {ACCOUNT_TYPE_LABELS[t]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Currency" required>
            <Select {...register('currency')}>
              {SUPPORTED_CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Country" required>
            <Select {...register('country')}>
              {COUNTRIES.map((c) => (
                <option key={c} value={c}>
                  {COUNTRY_LABELS[c]}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field
            label="Current balance"
            hint="Signed: liabilities negative"
            error={errors.current_balance?.message}
          >
            <Input type="number" step="0.01" {...register('current_balance')} />
          </Field>
          <Field label="Credit limit" hint="Optional">
            <Input type="number" step="0.01" {...register('credit_limit')} />
          </Field>
        </div>

        <Field label="Institution" hint="Optional">
          <Select {...register('institution_id')}>
            <option value="">None</option>
            {institutions.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name}
              </option>
            ))}
          </Select>
        </Field>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <Checkbox label="Include in net worth" {...register('include_in_net_worth')} />
          <Checkbox label="Include in liquid assets" {...register('include_in_liquid_assets')} />
          <Checkbox label="Protected reserve" {...register('is_protected_reserve')} />
        </div>

        <Field label="Notes" hint="Optional">
          <Textarea rows={2} {...register('notes')} />
        </Field>
      </form>
    </Dialog>
  );
}

const adjustSchema = z.object({
  new_balance: z.coerce.number(),
  as_of: z.string().min(1, 'Date is required'),
  note: z.string().optional(),
});
type AdjustValues = z.infer<typeof adjustSchema>;

function AdjustBalanceDialog({ account, onClose }: { account: Account | null; onClose: () => void }) {
  const adjust = useAdjustBalance();
  const toast = useToast();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AdjustValues>({
    resolver: zodResolver(adjustSchema),
    values: {
      new_balance: account?.current_balance ?? 0,
      as_of: todayISO(),
      note: '',
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    if (!account) return;
    try {
      await adjust.mutateAsync({ id: account.id, ...values });
      toast.success('Balance adjusted', 'A reconciliation entry was recorded.');
      onClose();
    } catch (err) {
      toast.error('Adjustment failed', err instanceof ApiError ? err.message : undefined);
    }
  });

  return (
    <Dialog
      open={!!account}
      onClose={onClose}
      title="Adjust balance"
      description={account ? `${account.name} · ${account.currency}` : undefined}
      size="sm"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={onSubmit} loading={adjust.isPending}>
            Apply adjustment
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="New balance" required error={errors.new_balance?.message}>
          <Input type="number" step="0.01" invalid={!!errors.new_balance} {...register('new_balance')} />
        </Field>
        <Field label="As of" required error={errors.as_of?.message}>
          <Input type="date" invalid={!!errors.as_of} {...register('as_of')} />
        </Field>
        <Field label="Note" hint="Optional">
          <Textarea rows={2} {...register('note')} />
        </Field>
      </form>
    </Dialog>
  );
}

const Checkbox = ({
  label,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) => (
  <label className="flex cursor-pointer items-center gap-2 rounded-md border border-border p-2.5 text-sm">
    <input
      type="checkbox"
      className="h-4 w-4 rounded border-input text-primary focus-ring"
      {...props}
    />
    <span>{label}</span>
  </label>
);
