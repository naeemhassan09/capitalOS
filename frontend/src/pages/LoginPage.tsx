import { useNavigate, useLocation } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ShieldCheck } from 'lucide-react';
import { useLogin } from '@/api/auth';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Field } from '@/components/ui/Label';
import { ThemeToggle } from '@/components/ui/ThemeToggle';

const schema = z.object({
  email: z.string().email('Enter a valid email'),
  password: z.string().min(1, 'Password is required'),
});

type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const login = useLogin();
  const toast = useToast();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await login.mutateAsync(values);
      const from = (location.state as { from?: string } | null)?.from || '/';
      navigate(from, { replace: true });
    } catch (err) {
      const message =
        err instanceof ApiError && err.status === 401
          ? 'Incorrect email or password.'
          : err instanceof ApiError
            ? err.message
            : 'Sign in failed. Please try again.';
      toast.error('Could not sign in', message);
    }
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <ShieldCheck className="h-6 w-6" aria-hidden />
          </span>
          <h1 className="text-2xl font-semibold text-foreground">Welcome back</h1>
          <p className="mt-1 text-sm text-muted-foreground">Sign in to CapitalOS.</p>
        </div>

        <form
          onSubmit={onSubmit}
          className="space-y-4 rounded-lg border border-border bg-card p-6 shadow-sm"
        >
          <Field label="Email" htmlFor="email" required error={errors.email?.message}>
            <Input id="email" type="email" autoComplete="email" invalid={!!errors.email} {...register('email')} />
          </Field>
          <Field label="Password" htmlFor="password" required error={errors.password?.message}>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              invalid={!!errors.password}
              {...register('password')}
            />
          </Field>
          <Button type="submit" className="w-full" loading={isSubmitting || login.isPending}>
            Sign in
          </Button>
        </form>
      </div>
    </div>
  );
}
