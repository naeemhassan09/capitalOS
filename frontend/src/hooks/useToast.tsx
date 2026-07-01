/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { CheckCircle2, AlertTriangle, Info, X, XCircle } from 'lucide-react';
import { cn } from '@/utils/cn';

export type ToastVariant = 'success' | 'error' | 'warning' | 'info';

interface Toast {
  id: number;
  title: string;
  description?: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  toast: (t: Omit<Toast, 'id'>) => void;
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
  info: (title: string, description?: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 1;

const VARIANT_STYLES: Record<ToastVariant, string> = {
  success: 'border-success/40 bg-card',
  error: 'border-danger/40 bg-card',
  warning: 'border-warning/40 bg-card',
  info: 'border-info/40 bg-card',
};

const VARIANT_ICONS: Record<ToastVariant, ReactNode> = {
  success: <CheckCircle2 className="h-5 w-5 text-success" aria-hidden />,
  error: <XCircle className="h-5 w-5 text-danger" aria-hidden />,
  warning: <AlertTriangle className="h-5 w-5 text-warning" aria-hidden />,
  info: <Info className="h-5 w-5 text-info" aria-hidden />,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (t: Omit<Toast, 'id'>) => {
      const id = nextId++;
      setToasts((prev) => [...prev, { ...t, id }]);
      window.setTimeout(() => dismiss(id), 5000);
    },
    [dismiss],
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      toast,
      success: (title, description) => toast({ title, description, variant: 'success' }),
      error: (title, description) => toast({ title, description, variant: 'error' }),
      info: (title, description) => toast({ title, description, variant: 'info' }),
    }),
    [toast],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2"
        role="region"
        aria-label="Notifications"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={cn(
              'pointer-events-auto flex items-start gap-3 rounded-lg border p-3 shadow-lg animate-slide-up',
              VARIANT_STYLES[t.variant],
            )}
          >
            <div className="mt-0.5 shrink-0">{VARIANT_ICONS[t.variant]}</div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-foreground">{t.title}</p>
              {t.description && (
                <p className="mt-0.5 text-sm text-muted-foreground break-words">{t.description}</p>
              )}
            </div>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              className="shrink-0 rounded p-1 text-muted-foreground hover:text-foreground focus-ring"
              aria-label="Dismiss notification"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within a ToastProvider');
  return ctx;
}
