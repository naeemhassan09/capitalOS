import { AlertOctagon, RefreshCw } from 'lucide-react';
import { ApiError } from '@/api/client';
import { Button } from './Button';

export function ErrorState({
  error,
  onRetry,
  title = 'Something went wrong',
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  const message =
    error instanceof ApiError
      ? error.message
      : error instanceof Error
        ? error.message
        : 'An unexpected error occurred.';
  const requestId = error instanceof ApiError ? error.requestId : undefined;

  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-danger/30 bg-danger/5 p-8 text-center">
      <AlertOctagon className="h-8 w-8 text-danger" aria-hidden />
      <div className="space-y-1">
        <p className="font-medium text-foreground">{title}</p>
        <p className="max-w-md text-sm text-muted-foreground">{message}</p>
        {requestId && (
          <p className="text-xs text-muted-foreground/70">Request ID: {requestId}</p>
        )}
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="h-4 w-4" />
          Try again
        </Button>
      )}
    </div>
  );
}
