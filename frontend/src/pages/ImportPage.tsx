import { useMemo, useRef, useState } from 'react';
import {
  Upload,
  FileSpreadsheet,
  Download,
  Check,
  AlertTriangle,
  RotateCcw,
  ChevronRight,
} from 'lucide-react';
import {
  useImports,
  useImporters,
  useUploadImport,
  usePreviewImport,
  useCommitImport,
  useRollbackImport,
  downloadImportTemplate,
} from '@/api/imports';
import { useAccounts } from '@/api/accounts';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { formatMoney } from '@/utils/money';
import { formatDate, formatDateTime } from '@/utils/date';
import { cn } from '@/utils/cn';
import { PageHeader } from '@/components/PageHeader';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Select } from '@/components/ui/Select';
import { Field } from '@/components/ui/Label';
import { Badge } from '@/components/ui/Badge';
import { Alert } from '@/components/ui/Alert';
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
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import type { ImportBatch, ImportPreview, ImportStatus, Currency } from '@/types';

type Step = 'upload' | 'preview' | 'report';

const STATUS_VARIANT: Record<ImportStatus, 'secondary' | 'success' | 'warning' | 'danger' | 'info'> = {
  uploaded: 'info',
  previewed: 'info',
  committed: 'success',
  rolled_back: 'secondary',
  failed: 'danger',
};

export function ImportPage() {
  const [step, setStep] = useState<Step>('upload');
  const [accountId, setAccountId] = useState('');
  const [importerType, setImporterType] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [committed, setCommitted] = useState<ImportBatch | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const accounts = useAccounts();
  const importers = useImporters();
  const upload = useUploadImport();
  const previewMut = usePreviewImport();
  const commit = useCommitImport();
  const toast = useToast();

  const resetFlow = () => {
    setStep('upload');
    setFile(null);
    setBatch(null);
    setPreview(null);
    setCommitted(null);
    if (fileRef.current) fileRef.current.value = '';
  };

  const startUpload = async () => {
    if (!file || !accountId || !importerType) return;
    try {
      const b = await upload.mutateAsync({ file, account_id: accountId, importer_type: importerType });
      setBatch(b);
      const p = await previewMut.mutateAsync({ id: b.id });
      setPreview(p);
      setStep('preview');
    } catch (err) {
      toast.error('Upload failed', err instanceof ApiError ? err.message : undefined);
    }
  };

  const runCommit = async () => {
    if (!batch) return;
    try {
      const result = await commit.mutateAsync({ id: batch.id });
      setCommitted(result);
      setStep('report');
      toast.success('Import committed', `${result.imported_row_count ?? 0} transactions added.`);
    } catch (err) {
      toast.error('Commit failed', err instanceof ApiError ? err.message : undefined);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Import"
        description="Bring in bank statements. Duplicates are detected and categories suggested before anything is written."
        actions={
          <Button variant="outline" size="sm" onClick={() => downloadImportTemplate()}>
            <Download className="h-4 w-4" /> CSV template
          </Button>
        }
      />

      <Stepper step={step} />

      {step === 'upload' && (
        <Card>
          <CardHeader>
            <CardTitle>Upload statement</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Account" required>
                <Select value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                  <option value="">Select account…</option>
                  {(accounts.data ?? []).filter((a) => !a.is_archived).map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} ({a.currency})
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Importer" required>
                <Select value={importerType} onChange={(e) => setImporterType(e.target.value)}>
                  <option value="">Select importer…</option>
                  {(importers.data ?? []).map((imp) => (
                    <option key={imp.importer_type} value={imp.importer_type}>
                      {imp.display_name}
                      {imp.needs_mapping ? ' (needs mapping)' : ''}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>

            <Field label="File" required>
              <label
                className={cn(
                  'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-border p-8 text-center transition-colors hover:border-primary/50',
                  file && 'border-primary/50 bg-primary/5',
                )}
              >
                <FileSpreadsheet className="h-8 w-8 text-muted-foreground" />
                <span className="text-sm text-foreground">
                  {file ? file.name : 'Click to choose a CSV / statement file'}
                </span>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv,.tsv,.txt,.ofx,.qif,.xls,.xlsx"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </label>
            </Field>

            <div className="flex justify-end">
              <Button
                onClick={startUpload}
                disabled={!file || !accountId || !importerType}
                loading={upload.isPending || previewMut.isPending}
              >
                Upload & preview <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {step === 'preview' && preview && (
        <PreviewStep
          preview={preview}
          onBack={resetFlow}
          onCommit={runCommit}
          committing={commit.isPending}
        />
      )}

      {step === 'report' && committed && (
        <ReportStep batch={committed} onDone={resetFlow} />
      )}

      <BatchHistory />
    </div>
  );
}

function Stepper({ step }: { step: Step }) {
  const steps: { key: Step; label: string }[] = [
    { key: 'upload', label: 'Upload' },
    { key: 'preview', label: 'Preview' },
    { key: 'report', label: 'Report' },
  ];
  const activeIndex = steps.findIndex((s) => s.key === step);
  return (
    <ol className="flex items-center gap-2">
      {steps.map((s, i) => {
        const active = i === activeIndex;
        const done = i < activeIndex;
        return (
          <li key={s.key} className="flex items-center gap-2">
            <span
              className={cn(
                'flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold',
                active
                  ? 'bg-primary text-primary-foreground'
                  : done
                    ? 'bg-success text-success-foreground'
                    : 'bg-muted text-muted-foreground',
              )}
            >
              {done ? <Check className="h-4 w-4" /> : i + 1}
            </span>
            <span className={cn('text-sm', active ? 'font-medium text-foreground' : 'text-muted-foreground')}>
              {s.label}
            </span>
            {i < steps.length - 1 && <ChevronRight className="h-4 w-4 text-muted-foreground" />}
          </li>
        );
      })}
    </ol>
  );
}

function PreviewStep({
  preview,
  onBack,
  onCommit,
  committing,
}: {
  preview: ImportPreview;
  onBack: () => void;
  onCommit: () => void;
  committing: boolean;
}) {
  const cleanCount = preview.total - preview.duplicate_count - preview.rejected;
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Preview</CardTitle>
        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary">{preview.total} rows</Badge>
          <Badge variant="success">{cleanCount} new</Badge>
          <Badge variant="warning">{preview.duplicate_count} duplicate</Badge>
          {preview.rejected > 0 && <Badge variant="danger">{preview.rejected} rejected</Badge>}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {preview.rejected > 0 && (
          <Alert variant="warning" title={`${preview.rejected} row(s) have validation issues`}>
            Rows with errors will be skipped on commit.
          </Alert>
        )}
        <TableContainer>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Merchant</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead>Suggested category</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {preview.rows.length === 0 ? (
                <TableEmpty colSpan={6}>No rows parsed.</TableEmpty>
              ) : (
                preview.rows.slice(0, 100).map((row, i) => {
                  const amount =
                    row.amount != null
                      ? row.direction === 'debit'
                        ? -Math.abs(row.amount)
                        : row.amount
                      : null;
                  return (
                    <TableRow key={i} className={row.error ? 'bg-danger/5' : undefined}>
                      <TableCell className="whitespace-nowrap">{formatDate(row.booking_date)}</TableCell>
                      <TableCell className="max-w-[220px] truncate">{row.description ?? '—'}</TableCell>
                      <TableCell className="max-w-[140px] truncate">{row.merchant ?? '—'}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {amount != null ? formatMoney(amount, (row.currency as Currency) ?? 'EUR', { signDisplay: 'always' }) : '—'}
                      </TableCell>
                      <TableCell>
                        {row.suggested_category ? (
                          <Badge variant="info">{row.suggested_category}</Badge>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {row.error ? (
                          <Badge variant="danger" title={row.error}>
                            <AlertTriangle className="h-3 w-3" /> Error
                          </Badge>
                        ) : row.is_duplicate ? (
                          <Badge variant="warning">Duplicate</Badge>
                        ) : (
                          <Badge variant="success">New</Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </TableContainer>
        {preview.rows.length > 100 && (
          <p className="text-xs text-muted-foreground">Showing first 100 of {preview.rows.length} parsed rows.</p>
        )}

        <div className="flex justify-between">
          <Button variant="outline" onClick={onBack}>
            Start over
          </Button>
          <Button onClick={onCommit} loading={committing} disabled={cleanCount === 0}>
            Commit {cleanCount} transaction{cleanCount === 1 ? '' : 's'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ReportStep({ batch, onDone }: { batch: ImportBatch; onDone: () => void }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Import complete</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert variant="success" title="Statement imported successfully" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Imported" value={batch.imported_row_count ?? 0} tone="text-success" />
          <Stat label="Duplicates skipped" value={batch.duplicate_row_count ?? 0} tone="text-warning" />
          <Stat label="Rejected" value={batch.rejected_row_count ?? 0} tone="text-danger" />
          <Stat label="Status" value={batch.status} tone="text-foreground" />
        </div>
        <div className="flex justify-end">
          <Button onClick={onDone}>Import another file</Button>
        </div>
      </CardContent>
    </Card>
  );
}

function Stat({ label, value, tone }: { label: string; value: string | number; tone: string }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn('mt-1 text-xl font-semibold tabular-nums', tone)}>{value}</p>
    </div>
  );
}

function BatchHistory() {
  const imports = useImports();
  const rollback = useRollbackImport();
  const toast = useToast();
  const [rollingBack, setRollingBack] = useState<ImportBatch | null>(null);

  const rows = useMemo(
    () => (imports.data ?? []).slice().sort((a, b) => (a.created_at < b.created_at ? 1 : -1)),
    [imports.data],
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Import history</CardTitle>
      </CardHeader>
      <CardContent>
        {imports.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : rows.length === 0 ? (
          <EmptyState icon={<Upload className="h-8 w-8" />} title="No imports yet" className="border-0" />
        ) : (
          <TableContainer>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>File</TableHead>
                  <TableHead>Importer</TableHead>
                  <TableHead className="text-right">Imported</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((b) => (
                  <TableRow key={b.id}>
                    <TableCell className="whitespace-nowrap">{formatDateTime(b.created_at)}</TableCell>
                    <TableCell className="max-w-[180px] truncate">{b.filename}</TableCell>
                    <TableCell>{b.importer_type}</TableCell>
                    <TableCell className="text-right tabular-nums">{b.imported_row_count ?? '—'}</TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANT[b.status]}>{b.status}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {b.status === 'committed' && (
                        <Button variant="ghost" size="sm" className="text-danger" onClick={() => setRollingBack(b)}>
                          <RotateCcw className="h-4 w-4" /> Rollback
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </CardContent>

      <ConfirmDialog
        open={!!rollingBack}
        onClose={() => setRollingBack(null)}
        title="Rollback this import?"
        description={
          rollingBack
            ? `All transactions from "${rollingBack.filename}" will be removed. This cannot be undone.`
            : ''
        }
        confirmLabel="Rollback"
        confirmVariant="destructive"
        loading={rollback.isPending}
        onConfirm={async () => {
          if (!rollingBack) return;
          try {
            await rollback.mutateAsync(rollingBack.id);
            toast.success('Import rolled back');
            setRollingBack(null);
          } catch (err) {
            toast.error('Rollback failed', err instanceof ApiError ? err.message : undefined);
          }
        }}
      />
    </Card>
  );
}
