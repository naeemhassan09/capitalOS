import { useState } from 'react';
import { Landmark, Link2, RefreshCw, Trash2 } from 'lucide-react';
import {
  useAspsps,
  useBankConnections,
  useBankStatus,
  useConnectBank,
  useDeleteBankConnection,
  useDiscoveredAccounts,
  useSyncBankConnection,
} from '@/api/bankConnections';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { formatDate, formatDateTime } from '@/utils/date';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge, type BadgeVariant } from '@/components/ui/Badge';
import { Alert } from '@/components/ui/Alert';
import { Dialog } from '@/components/ui/Dialog';
import { Select } from '@/components/ui/Select';
import { Field } from '@/components/ui/Label';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { BankAccountMappingForm } from '@/components/BankAccountMappingForm';
import type { BankConnection, BankConnectionStatus } from '@/types';

const COUNTRIES = ['IE', 'GB', 'DE', 'FR', 'ES', 'IT', 'NL', 'BE', 'PT', 'PL', 'LT', 'EE'];

const STATUS_BADGES: Record<BankConnectionStatus, BadgeVariant> = {
  pending: 'secondary',
  active: 'success',
  expired: 'warning',
  revoked: 'danger',
};

export function BankConnectionsSection() {
  const status = useBankStatus();

  if (status.isLoading) return <Skeleton className="h-40 w-full" />;
  if (!status.data?.configured) return <NotConfiguredCard />;

  return (
    <div className="space-y-6">
      <ConnectCard />
      <ConnectionsCard />
    </div>
  );
}

function NotConfiguredCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Landmark className="h-5 w-5 text-primary" /> Bank connections
          <Badge variant="secondary">Not configured</Badge>
        </CardTitle>
        <CardDescription>
          Connect AIB, Revolut and other banks via Enable Banking to sync balances and
          transactions automatically.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-muted-foreground">
        <p>To activate the integration on this server:</p>
        <ol className="list-decimal space-y-1 pl-5">
          <li>
            Register an application at{' '}
            <span className="font-medium text-foreground">enablebanking.com</span> and download
            its RSA private key.
          </li>
          <li>
            Place the key at <code className="text-foreground">secrets/enablebanking.pem</code>{' '}
            (mounted read-only into the backend container).
          </li>
          <li>
            Set <code className="text-foreground">ENABLE_BANKING_APP_ID</code> in the backend{' '}
            <code className="text-foreground">.env</code> and restart the backend.
          </li>
        </ol>
        <p>No keys or bank credentials are ever stored in the browser.</p>
      </CardContent>
    </Card>
  );
}

function ConnectCard() {
  const [country, setCountry] = useState('IE');
  const [bank, setBank] = useState('');
  const aspsps = useAspsps(country, true);
  const connect = useConnectBank();
  const toast = useToast();

  const banks = aspsps.data ?? [];

  const startConnect = async () => {
    if (!bank) return;
    try {
      const res = await connect.mutateAsync({ aspsp_name: bank, aspsp_country: country });
      window.location.href = res.url; // continue at the bank, back via /bank-callback
    } catch (err) {
      toast.error('Could not start bank authorisation',
        err instanceof ApiError ? err.message : undefined);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Landmark className="h-5 w-5 text-primary" /> Connect a bank
        </CardTitle>
        <CardDescription>
          You will be redirected to your bank to authorise read-only access (valid for 180
          days), then brought back here to map accounts.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Country" className="w-28">
            <Select
              value={country}
              onChange={(e) => {
                setCountry(e.target.value);
                setBank('');
              }}
            >
              {COUNTRIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Bank" className="w-full max-w-sm">
            <Select
              value={bank}
              onChange={(e) => setBank(e.target.value)}
              disabled={aspsps.isLoading}
            >
              <option value="">
                {aspsps.isLoading ? 'Loading banks…' : 'Select a bank…'}
              </option>
              {banks.map((b) => (
                <option key={`${b.name}-${b.country}`} value={b.name}>
                  {b.name}
                </option>
              ))}
            </Select>
          </Field>
          <Button onClick={startConnect} disabled={!bank} loading={connect.isPending}>
            Connect
          </Button>
        </div>
        {aspsps.isError && (
          <p className="mt-3 text-sm text-danger">
            Could not load the bank list
            {aspsps.error instanceof ApiError ? `: ${aspsps.error.message}` : '.'}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function ConnectionsCard() {
  const connections = useBankConnections();
  const sync = useSyncBankConnection();
  const del = useDeleteBankConnection();
  const toast = useToast();
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<BankConnection | null>(null);
  const [mapping, setMapping] = useState<BankConnection | null>(null);

  const runSync = async (conn: BankConnection) => {
    setSyncingId(conn.id);
    try {
      const res = await sync.mutateAsync(conn.id);
      toast.success(
        `${conn.aspsp_name} synced`,
        `${res.transactions_created} new transactions, ${res.duplicates_skipped} duplicates skipped.`,
      );
    } catch (err) {
      toast.error('Sync failed', err instanceof ApiError ? err.message : undefined);
    } finally {
      setSyncingId(null);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Connected banks</CardTitle>
        <CardDescription>
          Balances are taken as reported by the bank; transactions import idempotently and run
          through your categorisation rules.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {connections.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : (connections.data ?? []).length === 0 ? (
          <EmptyState
            icon={<Landmark className="h-8 w-8" />}
            title="No banks connected"
            description="Use “Connect a bank” above to authorise your first connection."
          />
        ) : (
          (connections.data ?? []).map((conn) => (
            <div key={conn.id} className="rounded-lg border border-border p-4">
              <div className="flex flex-wrap items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 font-medium text-foreground">
                    {conn.aspsp_name}
                    <Badge variant={STATUS_BADGES[conn.status] ?? 'secondary'}>
                      {conn.status}
                    </Badge>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {conn.aspsp_country} · Valid until {formatDate(conn.valid_until)} · Last
                    synced {conn.last_synced_at ? formatDateTime(conn.last_synced_at) : 'never'}
                  </p>
                </div>
                <div className="flex gap-2">
                  {conn.status === 'active' && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => runSync(conn)}
                      loading={sync.isPending && syncingId === conn.id}
                    >
                      <RefreshCw className="h-4 w-4" /> Sync now
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-danger"
                    onClick={() => setDeleting(conn)}
                  >
                    <Trash2 className="h-4 w-4" /> Disconnect
                  </Button>
                </div>
              </div>

              {conn.links.length > 0 ? (
                <ul className="mt-3 space-y-1 border-t border-border pt-3">
                  {conn.links.map((link) => (
                    <li
                      key={link.id}
                      className="flex items-center gap-2 text-sm text-muted-foreground"
                    >
                      <Link2 className="h-3.5 w-3.5" aria-hidden />
                      <span className="text-foreground">{link.display_name}</span>
                      {link.identifier_masked && <span>{link.identifier_masked}</span>}
                      {link.currency && <span>· {link.currency}</span>}
                    </li>
                  ))}
                </ul>
              ) : (
                conn.status === 'active' && (
                  <Alert variant="info" className="mt-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-sm">
                        No CapitalOS accounts are mapped yet — nothing will sync until you map
                        them.
                      </span>
                      <Button size="sm" variant="outline" onClick={() => setMapping(conn)}>
                        Map accounts
                      </Button>
                    </div>
                  </Alert>
                )
              )}
            </div>
          ))
        )}
      </CardContent>

      {mapping && (
        <MapAccountsDialog connection={mapping} onClose={() => setMapping(null)} />
      )}
      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Disconnect bank?"
        description={
          deleting
            ? `${deleting.aspsp_name} will be removed along with its account mappings. Imported transactions are kept.`
            : ''
        }
        confirmLabel="Disconnect"
        confirmVariant="destructive"
        loading={del.isPending}
        onConfirm={async () => {
          if (!deleting) return;
          try {
            await del.mutateAsync(deleting.id);
            toast.success('Bank disconnected');
            setDeleting(null);
          } catch (err) {
            toast.error('Disconnect failed', err instanceof ApiError ? err.message : undefined);
          }
        }}
      />
    </Card>
  );
}

function MapAccountsDialog({
  connection,
  onClose,
}: {
  connection: BankConnection;
  onClose: () => void;
}) {
  const discovered = useDiscoveredAccounts(connection.id);

  return (
    <Dialog open onClose={onClose} title={`Map ${connection.aspsp_name} accounts`} size="lg">
      {discovered.isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : discovered.isError ? (
        <Alert variant="danger" title="Could not load bank accounts">
          {discovered.error instanceof ApiError
            ? discovered.error.message
            : 'Try reconnecting the bank.'}
        </Alert>
      ) : (
        <BankAccountMappingForm
          connectionId={connection.id}
          discovered={discovered.data ?? []}
          onDone={onClose}
          onCancel={onClose}
        />
      )}
    </Dialog>
  );
}
