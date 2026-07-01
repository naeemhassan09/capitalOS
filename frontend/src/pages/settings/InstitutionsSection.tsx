import { useEffect, useState } from 'react';
import { Plus, Trash2, Pencil } from 'lucide-react';
import {
  useInstitutions,
  useCreateInstitution,
  useUpdateInstitution,
  useDeleteInstitution,
} from '@/api/institutions';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { COUNTRY_LABELS } from '@/utils/labels';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
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
import type { Institution, Country, InstitutionType } from '@/types';

const TYPES: InstitutionType[] = ['bank', 'broker', 'pension', 'wallet', 'other'];
const COUNTRIES: Country[] = ['IE', 'PK', 'OTHER'];

export function InstitutionsSection() {
  const institutions = useInstitutions();
  const del = useDeleteInstitution();
  const toast = useToast();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Institution | null>(null);
  const [deleting, setDeleting] = useState<Institution | null>(null);

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between">
        <div>
          <CardTitle>Institutions</CardTitle>
          <CardDescription>Banks, brokers and wallets linked to your accounts.</CardDescription>
        </div>
        <Button size="sm" onClick={() => { setEditing(null); setFormOpen(true); }}>
          <Plus className="h-4 w-4" /> Add
        </Button>
      </CardHeader>
      <CardContent>
        {institutions.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <TableContainer>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Country</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {(institutions.data ?? []).length === 0 ? (
                  <TableEmpty colSpan={4}>No institutions.</TableEmpty>
                ) : (
                  (institutions.data ?? []).map((inst) => (
                    <TableRow key={inst.id}>
                      <TableCell className="font-medium text-foreground">{inst.name}</TableCell>
                      <TableCell className="capitalize">{inst.institution_type}</TableCell>
                      <TableCell>{COUNTRY_LABELS[inst.country]}</TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => { setEditing(inst); setFormOpen(true); }} aria-label="Edit">
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-danger" onClick={() => setDeleting(inst)} aria-label="Delete">
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

      <InstitutionFormDialog open={formOpen} onClose={() => setFormOpen(false)} institution={editing} />
      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Delete institution?"
        description={deleting ? `"${deleting.name}" will be removed.` : ''}
        confirmLabel="Delete"
        confirmVariant="destructive"
        loading={del.isPending}
        onConfirm={async () => {
          if (!deleting) return;
          try {
            await del.mutateAsync(deleting.id);
            toast.success('Institution deleted');
            setDeleting(null);
          } catch (err) {
            toast.error('Delete failed', err instanceof ApiError ? err.message : undefined);
          }
        }}
      />
    </Card>
  );
}

function InstitutionFormDialog({
  open,
  onClose,
  institution,
}: {
  open: boolean;
  onClose: () => void;
  institution: Institution | null;
}) {
  const create = useCreateInstitution();
  const update = useUpdateInstitution();
  const toast = useToast();
  const isEdit = !!institution;
  const [name, setName] = useState('');
  const [type, setType] = useState<InstitutionType>('bank');
  const [country, setCountry] = useState<Country>('IE');

  // Re-seed the form each time the dialog opens for a given record.
  useEffect(() => {
    if (!open) return;
    setName(institution?.name ?? '');
    setType(institution?.institution_type ?? 'bank');
    setCountry(institution?.country ?? 'IE');
  }, [open, institution]);

  const submit = async () => {
    if (!name.trim()) return;
    const payload = { name: name.trim(), institution_type: type, country };
    try {
      if (isEdit && institution) {
        await update.mutateAsync({ id: institution.id, ...payload });
        toast.success('Institution updated');
      } else {
        await create.mutateAsync(payload);
        toast.success('Institution added');
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
      title={isEdit ? 'Edit institution' : 'Add institution'}
      size="sm"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} loading={create.isPending || update.isPending} disabled={!name.trim()}>
            {isEdit ? 'Save' : 'Add'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Name" required>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Type">
            <Select value={type} onChange={(e) => setType(e.target.value as InstitutionType)}>
              {TYPES.map((t) => (
                <option key={t} value={t} className="capitalize">
                  {t}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Country">
            <Select value={country} onChange={(e) => setCountry(e.target.value as Country)}>
              {COUNTRIES.map((c) => (
                <option key={c} value={c}>
                  {COUNTRY_LABELS[c]}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      </div>
    </Dialog>
  );
}
