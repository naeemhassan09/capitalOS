import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { qk } from './queryKeys';
import type { ImportBatch, Importer, ImportPreview } from '@/types';

export function useImports() {
  return useQuery({
    queryKey: qk.imports.all,
    queryFn: () => api.get<ImportBatch[]>('/imports'),
  });
}

export function useImporters() {
  return useQuery({
    queryKey: qk.imports.importers,
    queryFn: () => api.get<Importer[]>('/imports/importers'),
    staleTime: 300_000,
  });
}

export function useImport(id: string | undefined) {
  return useQuery({
    queryKey: qk.imports.detail(id ?? ''),
    queryFn: () => api.get<ImportBatch>(`/imports/${id}`),
    enabled: !!id,
  });
}

export function useUploadImport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      file,
      account_id,
      importer_type,
    }: {
      file: File;
      account_id: string;
      importer_type: string;
    }) => {
      const form = new FormData();
      form.append('file', file);
      form.append('account_id', account_id);
      form.append('importer_type', importer_type);
      return api.post<ImportBatch>('/imports/upload', { formData: form });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.imports.all }),
  });
}

export function usePreviewImport() {
  return useMutation({
    mutationFn: ({ id, column_map }: { id: string; column_map?: Record<string, string> }) =>
      api.post<ImportPreview>(`/imports/${id}/preview`, {
        json: column_map ? { column_map } : {},
      }),
  });
}

export function useCommitImport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, column_map }: { id: string; column_map?: Record<string, string> }) =>
      api.post<ImportBatch>(`/imports/${id}/commit`, {
        json: column_map ? { column_map } : {},
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.imports.all });
      qc.invalidateQueries({ queryKey: ['transactions'] });
      qc.invalidateQueries({ queryKey: qk.dashboard.summary });
      qc.invalidateQueries({ queryKey: qk.accounts.all });
    },
  });
}

export function useRollbackImport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<ImportBatch>(`/imports/${id}/rollback`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.imports.all });
      qc.invalidateQueries({ queryKey: ['transactions'] });
      qc.invalidateQueries({ queryKey: qk.dashboard.summary });
      qc.invalidateQueries({ queryKey: qk.accounts.all });
    },
  });
}

/** Download the CSV import template. */
export function downloadImportTemplate() {
  return api.download('/imports/template', 'capitalos-import-template.csv');
}
