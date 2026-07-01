import { type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useSetupStatus, useMe } from '@/api/auth';
import { AuthProvider } from './AuthContext';

function FullScreenSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Loader2 className="h-8 w-8 animate-spin text-primary" aria-label="Loading" />
    </div>
  );
}

/**
 * Guard for the authenticated app.
 *   - setup-status.initialized === false → force /setup
 *   - /auth/me 401 (user is null) → /login
 *   - otherwise render the app with the user in context
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  const setupStatus = useSetupStatus();
  const me = useMe();

  if (setupStatus.isLoading || me.isLoading) return <FullScreenSpinner />;

  if (setupStatus.data && !setupStatus.data.initialized) {
    return <Navigate to="/setup" replace />;
  }

  if (!me.data) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <AuthProvider user={me.data}>{children}</AuthProvider>;
}

/**
 * Guard for public pages (login/setup): if the app is already initialized and
 * the user is authenticated, redirect into the app.
 */
export function RedirectIfAuthenticated({
  children,
  page,
}: {
  children: ReactNode;
  page: 'login' | 'setup';
}) {
  const setupStatus = useSetupStatus();
  const me = useMe();

  if (setupStatus.isLoading || me.isLoading) return <FullScreenSpinner />;

  const initialized = setupStatus.data?.initialized ?? false;

  // Setup page only makes sense before initialization.
  if (page === 'setup' && initialized) {
    return <Navigate to={me.data ? '/' : '/login'} replace />;
  }

  // Login page: if not yet initialized, go to setup first.
  if (page === 'login' && !initialized) {
    return <Navigate to="/setup" replace />;
  }

  if (me.data) return <Navigate to="/" replace />;

  return <>{children}</>;
}
