import { cn } from '@/utils/cn';

export interface TabItem {
  value: string;
  label: string;
  icon?: React.ReactNode;
}

export interface TabsProps {
  items: TabItem[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

/** Accessible horizontal tab list; scrolls on mobile. */
export function Tabs({ items, value, onChange, className }: TabsProps) {
  return (
    <div
      role="tablist"
      className={cn(
        'flex gap-1 overflow-x-auto border-b border-border scrollbar-thin',
        className,
      )}
    >
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            role="tab"
            type="button"
            aria-selected={active}
            onClick={() => onChange(item.value)}
            className={cn(
              'inline-flex shrink-0 items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition-colors focus-ring',
              active
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {item.icon}
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

/** Segmented control style (pill) for compact toggles like scenario/horizon. */
export function SegmentedControl<T extends string | number>({
  options,
  value,
  onChange,
  className,
  ariaLabel,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
  ariaLabel?: string;
}) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn('inline-flex rounded-md border border-border bg-muted p-0.5', className)}
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={String(opt.value)}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              'rounded px-3 py-1.5 text-sm font-medium transition-colors focus-ring',
              active
                ? 'bg-card text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
