import { useEffect, useMemo, useState } from 'react';
import { Plus, Trash2, FlaskConical, Pencil } from 'lucide-react';
import { useRules, useCreateRule, useUpdateRule, useDeleteRule, useTestRule } from '@/api/rules';
import { useFlatCategories } from '@/api/categories';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Field } from '@/components/ui/Label';
import { CategorySelect } from '@/components/CategorySelect';
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
import type { Rule, RuleMatchField, RuleOperator } from '@/types';

const MATCH_FIELDS: { value: RuleMatchField; label: string }[] = [
  { value: 'description', label: 'Description' },
  { value: 'merchant', label: 'Merchant' },
  { value: 'amount', label: 'Amount' },
  { value: 'account', label: 'Account' },
  { value: 'direction', label: 'Direction' },
];

const OPERATORS: { value: RuleOperator; label: string }[] = [
  { value: 'contains', label: 'contains' },
  { value: 'equals', label: 'equals' },
  { value: 'starts_with', label: 'starts with' },
  { value: 'ends_with', label: 'ends with' },
  { value: 'regex', label: 'regex' },
  { value: 'gt', label: '>' },
  { value: 'lt', label: '<' },
];

export function RulesSection() {
  const rules = useRules();
  const del = useDeleteRule();
  const test = useTestRule();
  const toast = useToast();
  const { flat: categories } = useFlatCategories();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Rule | null>(null);
  const [deleting, setDeleting] = useState<Rule | null>(null);

  const catName = useMemo(() => {
    const map = new Map(categories.map((c) => [c.id, c.label]));
    return (id: string | null) => (id ? map.get(id) ?? '—' : '—');
  }, [categories]);

  const ordered = useMemo(
    () => (rules.data ?? []).slice().sort((a, b) => a.priority - b.priority),
    [rules.data],
  );

  const runTest = async (rule: Rule) => {
    try {
      const res = await test.mutateAsync(rule.id);
      toast.info(`Rule "${rule.name}"`, `${res.matches} transaction(s) match.`);
    } catch (err) {
      toast.error('Test failed', err instanceof ApiError ? err.message : undefined);
    }
  };

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between">
        <div>
          <CardTitle>Rules</CardTitle>
          <CardDescription>Auto-categorise transactions. Lower priority runs first.</CardDescription>
        </div>
        <Button
          size="sm"
          onClick={() => {
            setEditing(null);
            setFormOpen(true);
          }}
        >
          <Plus className="h-4 w-4" /> Add rule
        </Button>
      </CardHeader>
      <CardContent>
        {rules.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <TableContainer>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-right">Pri</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Condition</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {ordered.length === 0 ? (
                  <TableEmpty colSpan={6}>No rules defined.</TableEmpty>
                ) : (
                  ordered.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="text-right tabular-nums">{r.priority}</TableCell>
                      <TableCell className="font-medium text-foreground">{r.name}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {r.match_field} {OPERATORS.find((o) => o.value === r.operator)?.label} "{r.match_value}"
                      </TableCell>
                      <TableCell>{catName(r.category_id)}</TableCell>
                      <TableCell>
                        <Badge variant={r.enabled ? 'success' : 'secondary'}>
                          {r.enabled ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => runTest(r)} aria-label="Test rule">
                            <FlaskConical className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => {
                              setEditing(r);
                              setFormOpen(true);
                            }}
                            aria-label="Edit rule"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-danger" onClick={() => setDeleting(r)} aria-label="Delete rule">
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

      <RuleFormDialog open={formOpen} onClose={() => setFormOpen(false)} rule={editing} />
      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Delete rule?"
        description={deleting ? `"${deleting.name}" will be removed.` : ''}
        confirmLabel="Delete"
        confirmVariant="destructive"
        loading={del.isPending}
        onConfirm={async () => {
          if (!deleting) return;
          try {
            await del.mutateAsync(deleting.id);
            toast.success('Rule deleted');
            setDeleting(null);
          } catch (err) {
            toast.error('Delete failed', err instanceof ApiError ? err.message : undefined);
          }
        }}
      />
    </Card>
  );
}

function RuleFormDialog({ open, onClose, rule }: { open: boolean; onClose: () => void; rule: Rule | null }) {
  const create = useCreateRule();
  const update = useUpdateRule();
  const toast = useToast();
  const isEdit = !!rule;

  const [form, setForm] = useState({
    name: '',
    priority: 100,
    match_field: 'description' as RuleMatchField,
    operator: 'contains' as RuleOperator,
    match_value: '',
    category_id: '',
    enabled: true,
  });

  // Sync when opening a different rule.
  useEffect(() => {
    if (!open) return;
    setForm({
      name: rule?.name ?? '',
      priority: rule?.priority ?? 100,
      match_field: rule?.match_field ?? 'description',
      operator: rule?.operator ?? 'contains',
      match_value: rule?.match_value ?? '',
      category_id: rule?.category_id ?? '',
      enabled: rule?.enabled ?? true,
    });
  }, [open, rule]);

  const submit = async () => {
    if (!form.name.trim() || !form.match_value.trim()) return;
    const payload = { ...form, category_id: form.category_id || null };
    try {
      if (isEdit && rule) {
        await update.mutateAsync({ id: rule.id, ...payload });
        toast.success('Rule updated');
      } else {
        await create.mutateAsync(payload);
        toast.success('Rule created');
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
      title={isEdit ? 'Edit rule' : 'New rule'}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} loading={create.isPending || update.isPending}>
            {isEdit ? 'Save' : 'Create'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="Name" required className="sm:col-span-2">
            <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          </Field>
          <Field label="Priority" required>
            <Input type="number" value={form.priority} onChange={(e) => setForm((f) => ({ ...f, priority: Number(e.target.value) }))} />
          </Field>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="Field">
            <Select value={form.match_field} onChange={(e) => setForm((f) => ({ ...f, match_field: e.target.value as RuleMatchField }))}>
              {MATCH_FIELDS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Operator">
            <Select value={form.operator} onChange={(e) => setForm((f) => ({ ...f, operator: e.target.value as RuleOperator }))}>
              {OPERATORS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Value" required>
            <Input value={form.match_value} onChange={(e) => setForm((f) => ({ ...f, match_value: e.target.value }))} />
          </Field>
        </div>
        <Field label="Assign category">
          <CategorySelect value={form.category_id} onChange={(e) => setForm((f) => ({ ...f, category_id: e.target.value }))} />
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-input text-primary focus-ring"
            checked={form.enabled}
            onChange={(e) => setForm((f) => ({ ...f, enabled: e.target.checked }))}
          />
          Enabled
        </label>
      </div>
    </Dialog>
  );
}
