import { type HTMLAttributes } from 'react';
import { cn } from '@/utils/cn';

export type BadgeVariant =
  | 'default'
  | 'secondary'
  | 'outline'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'
  | 'settled'
  | 'pending'
  | 'projected'
  | 'protected'
  | 'deployable'
  | 'invested'
  | 'illiquid';

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  default: 'border-transparent bg-primary/15 text-primary',
  secondary: 'border-transparent bg-secondary text-secondary-foreground',
  outline: 'border-border text-foreground',
  success: 'border-transparent bg-success/15 text-success',
  warning: 'border-transparent bg-warning/20 text-warning',
  danger: 'border-transparent bg-danger/15 text-danger',
  info: 'border-transparent bg-info/15 text-info',
  settled: 'border-transparent bg-settled/15 text-settled',
  pending: 'border-transparent bg-pending/20 text-pending',
  projected: 'border-transparent bg-projected/15 text-projected',
  protected: 'border-transparent bg-protected/15 text-protected',
  deployable: 'border-transparent bg-deployable/15 text-deployable',
  invested: 'border-transparent bg-invested/15 text-invested',
  illiquid: 'border-transparent bg-illiquid/15 text-illiquid',
};

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
        VARIANT_CLASSES[variant],
        className,
      )}
      {...props}
    />
  );
}
