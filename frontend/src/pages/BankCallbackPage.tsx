import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Landmark, Loader2 } from 'lucide-react';
import { useCompleteBankAuth } from '@/api/bankConnections';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { PageHeader } from '@/components/PageHeader';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { BankAccountMappingForm } from '@/components/BankAccountMappingForm';
import type { CompleteBankAuthResponse } from '@/types';

/**
 * Landing page for the Enable Banking redirect (?code=…&state=…).
 * Exchanges the code for a session, then lets the user map each discovered
 * bank account onto an existing CapitalOS account (or skip it).
 */
export function BankCallbackPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const complete = useCompleteBankAuth();
  const startedRef = useRef(false); // guard against StrictMode double-run

  const code = params.get('code');
  const state = params.get('state');
  const bankError = params.get('error');

  const [result, setResult] = useState<CompleteBankAuthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    if (bankError) {
      setError(`The bank reported an error: ${bankError}`);
      return;
    }
    if (!code || !state) {
      setError('Missing code or state in the callback URL — the bank authorisation did not complete.');
      return;
    }
    complete
      .mutateAsync({ code, state })
      .then(setResult)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'Could not complete the bank authorisation.');
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const finish = () => {
    toast.success('Bank connected', result ? `${result.aspsp_name} is ready to sync.` : undefined);
    navigate('/settings', { replace: true });
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Bank authorisation"
        description="Finishing the connection with your bank."
      />

      {error ? (
        <Alert variant="danger" title="Bank connection failed">
          <p className="text-sm">{error}</p>
          <Button
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() => navigate('/settings', { replace: true })}
          >
            Back to settings
          </Button>
        </Alert>
      ) : !result ? (
        <Card>
          <CardContent className="flex items-center gap-3 py-10 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
            Completing authorisation with the bank…
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Landmark className="h-5 w-5 text-primary" /> {result.aspsp_name} connected
            </CardTitle>
            <CardDescription>
              Map each bank account to a CapitalOS account. Skipped accounts can be mapped later
              from Settings → Bank connections.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <BankAccountMappingForm
              connectionId={result.connection_id}
              discovered={result.accounts}
              onDone={finish}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
