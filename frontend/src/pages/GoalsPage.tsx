import { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Plus, Pencil, Trash2, Target } from 'lucide-react';
import { useGoals, useCreateGoal, useUpdateGoal, useDeleteGoal } from '@/api/goals';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { formatMoney, SUPPORTED_CURRENCIES } from '@/utils/money';
import { formatDate } from '@/utils/date';
import { PageHeader } from '@/components/PageHeader';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Progress } from '@/components/ui/Progress';
import { Dialog } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { Field } from '@/components/ui/Label';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { SkeletonCards } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { EmptyState } from '@/components/ui/EmptyState';
import type { GoalWithProgress, Currency } from '@/types';

const goalSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  target_amount: z.coerce.number().positive('Enter a positive target'),
  currency: z.enum(['EUR', 'PKR', 'USD', 'GBP', 'SAR']),
  target_date: z.string().optional(),
  priority: z.coerce.number().int().min(1),
  current_amount: z.coerce.number().min(0).optional(),
  notes: z.string().optional(),
});
type GoalFormValues = z.infer<typeof goalSchema>;

export function GoalsPage() {
  const goals = useGoals();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<GoalWithProgress | null>(null);
  const [deleting, setDeleting] = useState<GoalWithProgress | null>(null);

  const ordered = useMemo(
    () => (goals.data ?? []).slice().sort((a, b) => a.goal.priority - b.goal.priority),
    [goals.data],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Goals"
        description="Ordered by priority. Progress uses linked balances and required monthly contribution to target date."
        actions={
          <Button
            size="sm"
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <Plus className="h-4 w-4" /> New goal
          </Button>
        }
      />

      {goals.isLoading ? (
        <SkeletonCards count={3} />
      ) : goals.isError ? (
        <ErrorState error={goals.error} onRetry={() => goals.refetch()} />
      ) : ordered.length === 0 ? (
        <EmptyState
          icon={<Target className="h-10 w-10" />}
          title="No goals yet"
          description="Set savings targets and CapitalOS will track funding and flag ones at risk."
          action={
            <Button
              onClick={() => {
                setEditing(null);
                setFormOpen(true);
              }}
            >
              <Plus className="h-4 w-4" /> New goal
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {ordered.map((item) => (
            <GoalCard
              key={item.goal.id}
              item={item}
              onEdit={() => {
                setEditing(item);
                setFormOpen(true);
              }}
              onDelete={() => setDeleting(item)}
            />
          ))}
        </div>
      )}

      <GoalFormDialog open={formOpen} onClose={() => setFormOpen(false)} goal={editing} />
      <DeleteGoalDialog goal={deleting} onClose={() => setDeleting(null)} />
    </div>
  );
}

function GoalCard({
  item,
  onEdit,
  onDelete,
}: {
  item: GoalWithProgress;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const { goal, progress } = item;
  // Backend reports percent_funded on a 0..100 scale.
  const pct = Math.max(0, Math.min(100, Math.round(progress.percent_funded)));
  return (
    <Card>
      <CardContent className="pt-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Badge variant="secondary">P{goal.priority}</Badge>
              <p className="truncate font-medium text-foreground">{goal.name}</p>
            </div>
            {goal.target_date && (
              <p className="mt-0.5 text-xs text-muted-foreground">
                Target {formatDate(goal.target_date)}
                {progress.days_remaining != null && ` · ${progress.days_remaining} days left`}
              </p>
            )}
          </div>
          <Badge variant={progress.on_track ? 'success' : 'warning'}>
            {progress.on_track ? 'On track' : 'At risk'}
          </Badge>
        </div>

        <div className="mt-4">
          <Progress
            value={pct}
            indicatorClassName={progress.on_track ? 'bg-deployable' : 'bg-warning'}
            label={`${goal.name} progress`}
          />
          <div className="mt-1.5 flex items-center justify-between text-sm">
            <span className="font-medium text-foreground">
              {formatMoney(progress.current_amount, goal.currency)}
            </span>
            <span className="text-muted-foreground">
              of {formatMoney(goal.target_amount, goal.currency)} · {pct}%
            </span>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-md bg-muted/50 p-2.5">
            <p className="text-xs text-muted-foreground">Remaining</p>
            <p className="font-semibold tabular-nums text-foreground">
              {formatMoney(progress.remaining_amount, goal.currency)}
            </p>
          </div>
          <div className="rounded-md bg-muted/50 p-2.5">
            <p className="text-xs text-muted-foreground">Required / month</p>
            <p className="font-semibold tabular-nums text-foreground">
              {formatMoney(progress.required_monthly_contribution, goal.currency)}
            </p>
          </div>
        </div>

        <div className="mt-4 flex gap-2">
          <Button variant="outline" size="sm" onClick={onEdit}>
            <Pencil className="h-3.5 w-3.5" /> Edit
          </Button>
          <Button variant="ghost" size="sm" className="text-danger" onClick={onDelete}>
            <Trash2 className="h-3.5 w-3.5" /> Delete
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function GoalFormDialog({
  open,
  onClose,
  goal,
}: {
  open: boolean;
  onClose: () => void;
  goal: GoalWithProgress | null;
}) {
  const create = useCreateGoal();
  const update = useUpdateGoal();
  const toast = useToast();
  const isEdit = !!goal;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<GoalFormValues>({
    resolver: zodResolver(goalSchema),
    values: {
      name: goal?.goal.name ?? '',
      target_amount: goal?.goal.target_amount ?? 0,
      currency: (goal?.goal.currency ?? 'EUR') as Currency,
      target_date: goal?.goal.target_date ?? '',
      priority: goal?.goal.priority ?? 1,
      current_amount: goal?.goal.current_amount ?? 0,
      notes: goal?.goal.notes ?? '',
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    const payload = { ...values, target_date: values.target_date || null, notes: values.notes || null };
    try {
      if (isEdit && goal) {
        await update.mutateAsync({ id: goal.goal.id, ...payload });
        toast.success('Goal updated');
      } else {
        await create.mutateAsync(payload);
        toast.success('Goal created');
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
      title={isEdit ? 'Edit goal' : 'New goal'}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={onSubmit} loading={create.isPending || update.isPending}>
            {isEdit ? 'Save' : 'Create goal'}
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Name" required error={errors.name?.message}>
          <Input invalid={!!errors.name} {...register('name')} />
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Target amount" required error={errors.target_amount?.message}>
            <Input type="number" step="0.01" invalid={!!errors.target_amount} {...register('target_amount')} />
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
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="Current amount" hint="Optional">
            <Input type="number" step="0.01" {...register('current_amount')} />
          </Field>
          <Field label="Target date" hint="Optional">
            <Input type="date" {...register('target_date')} />
          </Field>
          <Field label="Priority" required error={errors.priority?.message}>
            <Input type="number" min={1} {...register('priority')} />
          </Field>
        </div>
        <Field label="Notes" hint="Optional">
          <Textarea rows={2} {...register('notes')} />
        </Field>
      </form>
    </Dialog>
  );
}

function DeleteGoalDialog({ goal, onClose }: { goal: GoalWithProgress | null; onClose: () => void }) {
  const del = useDeleteGoal();
  const toast = useToast();
  return (
    <ConfirmDialog
      open={!!goal}
      onClose={onClose}
      title="Delete goal?"
      description={goal ? `"${goal.goal.name}" will be removed.` : ''}
      confirmLabel="Delete"
      confirmVariant="destructive"
      loading={del.isPending}
      onConfirm={async () => {
        if (!goal) return;
        try {
          await del.mutateAsync(goal.goal.id);
          toast.success('Goal deleted');
          onClose();
        } catch (err) {
          toast.error('Delete failed', err instanceof ApiError ? err.message : undefined);
        }
      }}
    />
  );
}
