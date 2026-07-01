import { type ReactNode } from 'react';
import { ArrowDownRight, ArrowUpRight } from 'lucide-react';
import { cn } from '@/utils/cn';
import { Card } from '@/components/ui/Card';

export type MetricTone = 'default' | 'positive' | 'negative' | 'protected' | 'deployable' | 'muted';

const TONE_ACCENT: Record<MetricTone, string> = {
  default: 'text-foreground',
  positive: 'text-positive',
  negative: 'text-negative',
  protected: 'text-protected',
  deployable: 'text-deployable',
  muted: 'text-muted-foreground',
};

export function MetricCard({
  label,
  value,
  sub,
  tone = 'default',
  icon,
  prominent = false,
  delta,
  className,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: MetricTone;
  icon?: ReactNode;
  prominent?: boolean;
  delta?: { value: string; positive: boolean };
  className?: string;
}) {
  // Prominent + negative deployable must read as danger, never green.
  const isNegativeProminent = prominent && tone === 'negative';

  return (
    <Card
      className={cn(
        'p-4',
        prominent && 'ring-1',
        prominent && tone === 'deployable' && 'ring-deployable/40 bg-deployable/5',
        isNegativeProminent && 'ring-danger/50 bg-danger/5',
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p
          className={cn(
            'text-xs font-medium uppercase tracking-wide text-muted-foreground',
            prominent && 'text-[13px]',
          )}
        >
          {label}
        </p>
        {icon && <span className="text-muted-foreground">{icon}</span>}
      </div>
      <p
        className={cn(
          'mt-2 font-semibold tabular-nums',
          prominent ? 'text-3xl' : 'text-2xl',
          isNegativeProminent ? 'text-danger' : TONE_ACCENT[tone],
        )}
      >
        {value}
      </p>
      <div className="mt-1 flex items-center gap-2">
        {delta && (
          <span
            className={cn(
              'inline-flex items-center gap-0.5 text-xs font-medium',
              delta.positive ? 'text-positive' : 'text-negative',
            )}
          >
            {delta.positive ? (
              <ArrowUpRight className="h-3 w-3" />
            ) : (
              <ArrowDownRight className="h-3 w-3" />
            )}
            {delta.value}
          </span>
        )}
        {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      </div>
    </Card>
  );
}
