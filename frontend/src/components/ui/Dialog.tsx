import { useEffect, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '@/utils/cn';

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}

const SIZE_CLASSES = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
};

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  className,
  size = 'md',
}: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    // Focus the panel for keyboard users.
    panelRef.current?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/50 animate-fade-in"
        onClick={onClose}
        aria-hidden
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={cn(
          'relative z-10 flex max-h-[90vh] w-full flex-col rounded-lg border border-border bg-card shadow-xl outline-none animate-slide-up',
          SIZE_CLASSES[size],
          className,
        )}
      >
        {(title || description) && (
          <div className="flex items-start justify-between gap-4 border-b border-border p-4 sm:p-5">
            <div className="min-w-0">
              {title && <h2 className="text-lg font-semibold text-foreground">{title}</h2>}
              {description && (
                <p className="mt-1 text-sm text-muted-foreground">{description}</p>
              )}
            </div>
            <button
              type="button"
              onClick={onClose}
              className="shrink-0 rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground focus-ring"
              aria-label="Close dialog"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        )}
        <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5 scrollbar-thin">{children}</div>
        {footer && (
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border p-4 sm:p-5">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}
