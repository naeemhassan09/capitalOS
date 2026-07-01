import { Download, Upload, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import { exportsApi } from '@/api/exports';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Alert } from '@/components/ui/Alert';

export function DataSection() {
  const toast = useToast();

  const doExport = async (fn: () => Promise<void>, label: string) => {
    try {
      await fn();
    } catch (err) {
      toast.error(`Could not export ${label}`, err instanceof ApiError ? err.message : undefined);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" /> Your data, your control
          </CardTitle>
          <CardDescription>CapitalOS is privacy-first. Export everything at any time.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="mb-2 text-sm font-medium text-foreground">Full backup</p>
            <Button variant="outline" size="sm" onClick={() => doExport(exportsApi.full, 'full backup')}>
              <Download className="h-4 w-4" /> Download full backup (JSON)
            </Button>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-foreground">CSV exports</p>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => doExport(exportsApi.transactions, 'transactions')}>
                <Download className="h-4 w-4" /> Transactions
              </Button>
              <Button variant="outline" size="sm" onClick={() => doExport(exportsApi.accounts, 'accounts')}>
                <Download className="h-4 w-4" /> Accounts
              </Button>
              <Button variant="outline" size="sm" onClick={() => doExport(exportsApi.goals, 'goals')}>
                <Download className="h-4 w-4" /> Goals
              </Button>
              <Button variant="outline" size="sm" onClick={() => doExport(exportsApi.holdings, 'holdings')}>
                <Download className="h-4 w-4" /> Holdings
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Import data</CardTitle>
          <CardDescription>Bring in bank statements and transactions.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link
            to="/import"
            className="inline-flex h-8 items-center gap-2 rounded-md border border-input px-3 text-xs font-medium text-foreground transition-colors hover:bg-accent focus-ring"
          >
            <Upload className="h-4 w-4" /> Go to Import
          </Link>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Two-factor authentication</CardTitle>
          <CardDescription>Add a TOTP authenticator for extra security.</CardDescription>
        </CardHeader>
        <CardContent>
          <Alert variant="info" title="Coming soon">
            TOTP-based two-factor authentication will be available in a future update.
          </Alert>
        </CardContent>
      </Card>
    </div>
  );
}
