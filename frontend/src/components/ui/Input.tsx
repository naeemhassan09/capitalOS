import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '@/utils/cn';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, invalid, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        'flex h-10 w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground shadow-sm transition-colors',
        'placeholder:text-muted-foreground',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background',
        'disabled:cursor-not-allowed disabled:opacity-50',
        'file:border-0 file:bg-transparent file:text-sm file:font-medium',
        invalid ? 'border-danger focus-visible:ring-danger' : 'border-input',
        className,
      )}
      {...props}
    />
  );
});
