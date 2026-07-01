import { useState } from 'react';
import { Plus, Trash2, ChevronRight } from 'lucide-react';
import {
  useCategories,
  useCreateCategory,
  useDeleteCategory,
} from '@/api/categories';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Field } from '@/components/ui/Label';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Skeleton } from '@/components/ui/Skeleton';
import type { Category } from '@/types';

export function CategoriesSection() {
  const categories = useCategories();
  const del = useDeleteCategory();
  const toast = useToast();
  const [addOpen, setAddOpen] = useState(false);
  const [deleting, setDeleting] = useState<Category | null>(null);

  const flatParents: { id: string; label: string }[] = [];
  const collectParents = (nodes: Category[] | undefined, prefix: string) => {
    for (const n of nodes ?? []) {
      const label = prefix ? `${prefix} / ${n.name}` : n.name;
      flatParents.push({ id: n.id, label });
      collectParents(n.children, label);
    }
  };
  collectParents(categories.data, '');

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between">
        <div>
          <CardTitle>Categories</CardTitle>
          <CardDescription>Organise transactions into an income/expense tree.</CardDescription>
        </div>
        <Button size="sm" onClick={() => setAddOpen(true)}>
          <Plus className="h-4 w-4" /> Add
        </Button>
      </CardHeader>
      <CardContent>
        {categories.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : (categories.data ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">No categories yet.</p>
        ) : (
          <ul className="space-y-1">
            {(categories.data ?? []).map((c) => (
              <CategoryNode key={c.id} node={c} depth={0} onDelete={setDeleting} />
            ))}
          </ul>
        )}
      </CardContent>

      <AddCategoryDialog open={addOpen} onClose={() => setAddOpen(false)} parents={flatParents} />
      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Delete category?"
        description={deleting ? `"${deleting.name}" and its rules links may be affected.` : ''}
        confirmLabel="Delete"
        confirmVariant="destructive"
        loading={del.isPending}
        onConfirm={async () => {
          if (!deleting) return;
          try {
            await del.mutateAsync(deleting.id);
            toast.success('Category deleted');
            setDeleting(null);
          } catch (err) {
            toast.error('Delete failed', err instanceof ApiError ? err.message : undefined);
          }
        }}
      />
    </Card>
  );
}

function CategoryNode({
  node,
  depth,
  onDelete,
}: {
  node: Category;
  depth: number;
  onDelete: (c: Category) => void;
}) {
  return (
    <>
      <li
        className="flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-muted/50"
        style={{ paddingLeft: 8 + depth * 20 }}
      >
        <div className="flex items-center gap-2">
          {depth > 0 && <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}
          <span className="text-sm text-foreground">{node.name}</span>
          {node.is_income && <Badge variant="success">Income</Badge>}
          {node.is_essential && <Badge variant="secondary">Essential</Badge>}
          {node.is_system && <Badge variant="outline">System</Badge>}
        </div>
        {!node.is_system && (
          <Button variant="ghost" size="icon" className="h-7 w-7 text-danger" onClick={() => onDelete(node)} aria-label="Delete category">
            <Trash2 className="h-4 w-4" />
          </Button>
        )}
      </li>
      {node.children.map((child) => (
        <CategoryNode key={child.id} node={child} depth={depth + 1} onDelete={onDelete} />
      ))}
    </>
  );
}

function AddCategoryDialog({
  open,
  onClose,
  parents,
}: {
  open: boolean;
  onClose: () => void;
  parents: { id: string; label: string }[];
}) {
  const create = useCreateCategory();
  const toast = useToast();
  const [name, setName] = useState('');
  const [parentId, setParentId] = useState('');
  const [isIncome, setIsIncome] = useState(false);
  const [isEssential, setIsEssential] = useState(false);

  const submit = async () => {
    if (!name.trim()) return;
    try {
      await create.mutateAsync({
        name: name.trim(),
        parent_id: parentId || null,
        is_income: isIncome,
        is_essential: isEssential,
      });
      toast.success('Category added');
      setName('');
      setParentId('');
      setIsIncome(false);
      setIsEssential(false);
      onClose();
    } catch (err) {
      toast.error('Add failed', err instanceof ApiError ? err.message : undefined);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Add category"
      size="sm"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} loading={create.isPending} disabled={!name.trim()}>
            Add
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Name" required>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Parent" hint="Optional">
          <Select value={parentId} onChange={(e) => setParentId(e.target.value)}>
            <option value="">Top level</option>
            {parents.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </Select>
        </Field>
        <div className="flex gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4 rounded border-input text-primary focus-ring" checked={isIncome} onChange={(e) => setIsIncome(e.target.checked)} />
            Income
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4 rounded border-input text-primary focus-ring" checked={isEssential} onChange={(e) => setIsEssential(e.target.checked)} />
            Essential
          </label>
        </div>
      </div>
    </Dialog>
  );
}
