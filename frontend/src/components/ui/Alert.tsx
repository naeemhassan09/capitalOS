import { type HTMLAttributes } from 'react';
import { AlertTriangle, Info, XCircle, CheckCircle2 } from 'lucide-react';
import { cn } from '@/utils/cn';

export type AlertVariant = 'info' | 'warning' | 'danger' | 'success';

export interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  variant?: AlertVariant;
  title?: string;
  icon?: boolean;
}

const VARIANT_CLASSES: Record<AlertVariant, string> = {
  info: 'border-info/40 bg-info/10 text-foreground',
  warning: 'border-warning/50 bg-warning/10 text-foreground',
  danger: 'border-danger/40 bg-danger/10 text-foreground',
  success: 'border-success/40 bg-success/10 text-foreground',
};

const ICON_CLASSES: Record<AlertVariant, string> = {
  info: 'text-info',
  warning: 'text-warning',
  danger: 'text-danger',
  success: 'text-success',
};

const ICONS: Record<AlertVariant, typeof Info> = {
  info: Info,
  warning: AlertTriangle,
  danger: XCircle,
  success: CheckCircle2,
};

export function Alert({
  className,
  variant = 'info',
  title,
  icon = true,
  children,
  ...props
}: AlertProps) {
  const Icon = ICONS[variant];
  return (
    <div
      role={variant === 'danger' ? 'alert' : 'status'}
      className={cn('flex gap-3 rounded-lg border p-3.5', VARIANT_CLASSES[variant], className)}
      {...props}
    >
      {icon && <Icon className={cn('mt-0.5 h-5 w-5 shrink-0', ICON_CLASSES[variant])} aria-hidden />}
      <div className="min-w-0 flex-1">
        {title && <p className="font-medium leading-snug">{title}</p>}
        {children && <div className={cn('text-sm', title && 'mt-0.5')}>{children}</div>}
      </div>
    </div>
  );
}
