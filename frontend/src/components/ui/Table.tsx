import { type HTMLAttributes, type TdHTMLAttributes, type ThHTMLAttributes } from 'react';
import { cn } from '@/utils/cn';

/** Scrollable wrapper so wide tables stay usable on mobile. */
export function TableContainer({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('w-full overflow-x-auto rounded-lg border border-border scrollbar-thin', className)}
      {...props}
    />
  );
}

export function Table({ className, ...props }: HTMLAttributes<HTMLTableElement>) {
  return <table className={cn('w-full caption-bottom text-sm', className)} {...props} />;
}

export function TableHeader({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={cn('bg-muted/50 [&_tr]:border-b', className)} {...props} />;
}

export function TableBody({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn('[&_tr:last-child]:border-0', className)} {...props} />;
}

export function TableRow({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn(
        'border-b border-border transition-colors hover:bg-muted/40 data-[selected=true]:bg-primary/5',
        className,
      )}
      {...props}
    />
  );
}

export function TableHead({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        'h-10 whitespace-nowrap px-3 text-left align-middle text-xs font-semibold uppercase tracking-wide text-muted-foreground',
        className,
      )}
      {...props}
    />
  );
}

export function TableCell({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn('px-3 py-2.5 align-middle', className)} {...props} />;
}

export function TableEmpty({ colSpan, children }: { colSpan: number; children: React.ReactNode }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-3 py-10 text-center text-sm text-muted-foreground">
        {children}
      </td>
    </tr>
  );
}
