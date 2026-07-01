import { useEffect, useState } from 'react';
import { Plus, Trash2, Pencil, ShieldCheck } from 'lucide-react';
import {
  useReserves,
  useCreateReserve,
  useUpdateReserve,
  useDeleteReserve,
} from '@/api/reserves';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { SUPPORTED_CURRENCIES, formatMoney } from '@/utils/money';
import { COUNTRY_LABELS } from '@/utils/labels';
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
import type { Reserve, Country, Currency } from '@/types';

const COUNTRIES: Country[] = ['IE', 'PK', 'OTHER'];

export function ReservesSection() {
  const reserves = useReserves();
  const del = useDeleteReserve();
  const toast = useToast();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Reserve | null>(null);
  const [deleting, setDeleting] = useState<Reserve | null>(null);

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-protected" /> Protected reserves
          </CardTitle>
          <CardDescription>
            Ring-fenced buffers. Protected amounts are excluded from deployable capital.
          </CardDescription>
        </div>
        <Button size="sm" onClick={() => { setEditing(null); setFormOpen(true); }}>
          <Plus className="h-4 w-4" /> Add reserve
        </Button>
      </CardHeader>
      <CardContent>
        {reserves.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <TableContainer>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Jurisdiction</TableHead>
                  <TableHead className="text-right">Target</TableHead>
                  <TableHead className="text-right">Protected</TableHead>
                  <TableHead>Floor</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {(reserves.data ?? []).length === 0 ? (
                  <TableEmpty colSpan={6}>No reserves defined.</TableEmpty>
                ) : (
                  (reserves.data ?? []).map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="font-medium text-foreground">{r.name}</TableCell>
                      <TableCell>{COUNTRY_LABELS[r.jurisdiction]}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatMoney(r.target_amount, r.currency)}</TableCell>
                      <TableCell className="text-right tabular-nums text-protected">{formatMoney(r.protected_amount, r.currency)}</TableCell>
                      <TableCell>{r.hard_floor ? <Badge variant="danger">Hard floor</Badge> : <Badge variant="secondary">Soft</Badge>}</TableCell>
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

      <ReserveFormDialog open={formOpen} onClose={() => setFormOpen(false)} reserve={editing} />
      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Delete reserve?"
        description={deleting ? `"${deleting.name}" will be removed.` : ''}
        confirmLabel="Delete"
        confirmVariant="destructive"
        loading={del.isPending}
        onConfirm={async () => {
          if (!deleting) return;
          try {
            await del.mutateAsync(deleting.id);
            toast.success('Reserve deleted');
            setDeleting(null);
          } catch (err) {
            toast.error('Delete failed', err instanceof ApiError ? err.message : undefined);
          }
        }}
      />
    </Card>
  );
}

function ReserveFormDialog({ open, onClose, reserve }: { open: boolean; onClose: () => void; reserve: Reserve | null }) {
  const create = useCreateReserve();
  const update = useUpdateReserve();
  const toast = useToast();
  const isEdit = !!reserve;
  const [form, setForm] = useState({
    name: '',
    jurisdiction: 'IE' as Country,
    currency: 'EUR' as Currency,
    target_amount: 0,
    protected_amount: 0,
    hard_floor: false,
  });

  useEffect(() => {
    if (!open) return;
    setForm({
      name: reserve?.name ?? '',
      jurisdiction: (reserve?.jurisdiction ?? 'IE') as Country,
      currency: (reserve?.currency ?? 'EUR') as Currency,
      target_amount: reserve?.target_amount ?? 0,
      protected_amount: reserve?.protected_amount ?? 0,
      hard_floor: reserve?.hard_floor ?? false,
    });
  }, [open, reserve]);

  const submit = async () => {
    if (!form.name.trim()) return;
    try {
      if (isEdit && reserve) {
        await update.mutateAsync({ id: reserve.id, ...form });
        toast.success('Reserve updated');
      } else {
        await create.mutateAsync(form);
        toast.success('Reserve added');
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
      title={isEdit ? 'Edit reserve' : 'Add reserve'}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} loading={create.isPending || update.isPending} disabled={!form.name.trim()}>
            {isEdit ? 'Save' : 'Add'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Name" required>
          <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Jurisdiction">
            <Select value={form.jurisdiction} onChange={(e) => setForm((f) => ({ ...f, jurisdiction: e.target.value as Country }))}>
              {COUNTRIES.map((c) => (
                <option key={c} value={c}>{COUNTRY_LABELS[c]}</option>
              ))}
            </Select>
          </Field>
          <Field label="Currency">
            <Select value={form.currency} onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value as Currency }))}>
              {SUPPORTED_CURRENCIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Target amount">
            <Input type="number" step="0.01" value={form.target_amount} onChange={(e) => setForm((f) => ({ ...f, target_amount: Number(e.target.value) || 0 }))} />
          </Field>
          <Field label="Protected amount" hint="Excluded from deployable">
            <Input type="number" step="0.01" value={form.protected_amount} onChange={(e) => setForm((f) => ({ ...f, protected_amount: Number(e.target.value) || 0 }))} />
          </Field>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="h-4 w-4 rounded border-input text-primary focus-ring" checked={form.hard_floor} onChange={(e) => setForm((f) => ({ ...f, hard_floor: e.target.checked }))} />
          Hard floor (cash must never drop below protected amount)
        </label>
      </div>
    </Dialog>
  );
}
