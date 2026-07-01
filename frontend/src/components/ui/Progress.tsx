import { cn } from '@/utils/cn';

export interface ProgressProps {
  value: number; // 0..100
  className?: string;
  indicatorClassName?: string;
  label?: string;
}

export function Progress({ value, className, indicatorClassName, label }: ProgressProps) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div
      className={cn('h-2 w-full overflow-hidden rounded-full bg-secondary', className)}
      role="progressbar"
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <div
        className={cn(
          'h-full rounded-full transition-all',
          indicatorClassName ?? 'bg-primary',
        )}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
