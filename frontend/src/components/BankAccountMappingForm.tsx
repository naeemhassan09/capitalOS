import { useMemo, useState } from 'react';
import { Link2 } from 'lucide-react';
import { useAccounts } from '@/api/accounts';
import { useCreateBankLinks } from '@/api/bankConnections';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import type { BankLinkMapping, DiscoveredBankAccount } from '@/types';

const SKIP = '';

/**
 * Maps each discovered bank account (name + masked identifier + currency —
 * cards have no IBAN, so the identifier is whatever the bank exposes) to an
 * existing CapitalOS account, with a per-row skip option.
 */
export function BankAccountMappingForm({
  connectionId,
  discovered,
  onDone,
  onCancel,
}: {
  connectionId: string;
  discovered: DiscoveredBankAccount[];
  onDone: () => void;
  onCancel?: () => void;
}) {
  const accounts = useAccounts();
  const createLinks = useCreateBankLinks();
  const toast = useToast();
  const [choices, setChoices] = useState<Record<string, string>>({});

  const options = useMemo(
    () => (accounts.data ?? []).filter((a) => !a.is_archived),
    [accounts.data],
  );

  const submit = async () => {
    const mappings: BankLinkMapping[] = discovered
      .filter((d) => (choices[d.uid] ?? SKIP) !== SKIP)
      .map((d) => ({
        external_uid: d.uid,
        account_id: choices[d.uid],
        display_name: d.name,
        identifier_masked: d.identifier_masked || null,
        currency: d.currency,
      }));
    if (mappings.length === 0) {
      toast.info('Nothing mapped', 'All bank accounts were skipped.');
      onDone();
      return;
    }
    try {
      await createLinks.mutateAsync({ connection_id: connectionId, mappings });
      toast.success(
        'Accounts mapped',
        `${mappings.length} bank account${mappings.length > 1 ? 's' : ''} linked.`,
      );
      onDone();
    } catch (err) {
      toast.error('Mapping failed', err instanceof ApiError ? err.message : undefined);
    }
  };

  if (accounts.isLoading) return <Skeleton className="h-32 w-full" />;

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        {discovered.map((d) => (
          <div
            key={d.uid}
            className="flex flex-wrap items-center gap-3 rounded-lg border border-border p-3"
          >
            <Link2 className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-foreground">{d.name}</p>
              <p className="text-xs text-muted-foreground">
                {d.identifier_masked || 'No identifier'}
                {d.currency ? ` · ${d.currency}` : ''}
              </p>
            </div>
            <div className="w-full sm:w-64">
              <Select
                value={choices[d.uid] ?? SKIP}
                onChange={(e) => setChoices((c) => ({ ...c, [d.uid]: e.target.value }))}
                aria-label={`CapitalOS account for ${d.name}`}
              >
                <option value={SKIP}>Skip — don't link</option>
                {options.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.currency})
                  </option>
                ))}
              </Select>
            </div>
          </div>
        ))}
        {discovered.length === 0 && (
          <p className="text-sm text-muted-foreground">
            The bank returned no accounts for this connection.
          </p>
        )}
      </div>
      {options.length === 0 && discovered.length > 0 && (
        <Badge variant="warning">Create a CapitalOS account first, then map it here.</Badge>
      )}
      <div className="flex justify-end gap-2">
        {onCancel && (
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button onClick={submit} loading={createLinks.isPending} disabled={discovered.length === 0}>
          Save mapping
        </Button>
      </div>
    </div>
  );
}
