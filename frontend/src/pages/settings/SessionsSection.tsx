import { Monitor, LogOut } from 'lucide-react';
import { useSessions, useRevokeSession } from '@/api/auth';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { formatRelative, formatDateTime } from '@/utils/date';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';

export function SessionsSection() {
  const sessions = useSessions();
  const revoke = useRevokeSession();
  const toast = useToast();

  const handleRevoke = async (id: string) => {
    try {
      await revoke.mutateAsync(id);
      toast.success('Session revoked');
    } catch (err) {
      toast.error('Could not revoke session', err instanceof ApiError ? err.message : undefined);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Active sessions</CardTitle>
        <CardDescription>Devices currently signed in to your account.</CardDescription>
      </CardHeader>
      <CardContent>
        {sessions.isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : (sessions.data ?? []).length === 0 ? (
          <EmptyState title="No active sessions" className="border-0" />
        ) : (
          <ul className="divide-y divide-border">
            {(sessions.data ?? []).map((s) => (
              <li key={s.id} className="flex items-center justify-between gap-3 py-3">
                <div className="flex min-w-0 items-center gap-3">
                  <Monitor className="h-5 w-5 shrink-0 text-muted-foreground" />
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 text-sm font-medium text-foreground">
                      <span className="truncate">{s.user_agent || 'Unknown device'}</span>
                      {s.is_current && <Badge variant="success">This device</Badge>}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {s.ip_address ? `${s.ip_address} · ` : ''}
                      Last active {formatRelative(s.last_seen_at ?? s.created_at)} · signed in{' '}
                      {formatDateTime(s.created_at)}
                    </p>
                  </div>
                </div>
                {!s.is_current && (
                  <Button variant="outline" size="sm" onClick={() => handleRevoke(s.id)} loading={revoke.isPending}>
                    <LogOut className="h-4 w-4" /> Revoke
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
