import { type HTMLAttributes, forwardRef } from 'react';
import { cn } from '@/utils/cn';

export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(function Card(
  { className, ...props },
  ref,
) {
  return (
    <div
      ref={ref}
      className={cn('rounded-lg border border-border bg-card text-card-foreground shadow-sm', className)}
      {...props}
    />
  );
});

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex flex-col gap-1 p-4 sm:p-5', className)} {...props} />;
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={cn('text-base font-semibold leading-none tracking-tight', className)} {...props} />
  );
}

export function CardDescription({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('text-sm text-muted-foreground', className)} {...props} />;
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-4 pt-0 sm:p-5 sm:pt-0', className)} {...props} />;
}

export function CardFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex items-center p-4 pt-0 sm:p-5 sm:pt-0', className)} {...props} />;
}
