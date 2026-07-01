import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ShieldCheck } from 'lucide-react';
import { useLogin, usePinLogin, useSetupStatus } from '@/api/auth';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Field } from '@/components/ui/Label';
import { ThemeToggle } from '@/components/ui/ThemeToggle';

const passwordSchema = z.object({
  email: z.string().email('Enter a valid email'),
  password: z.string().min(1, 'Password is required'),
});
type PasswordValues = z.infer<typeof passwordSchema>;

const pinSchema = z.object({
  pin: z.string().regex(/^\d{4,8}$/, 'Enter your 4–8 digit PIN'),
});
type PinValues = z.infer<typeof pinSchema>;

export function LoginPage() {
  const setupStatus = useSetupStatus();
  const pinEnabled = setupStatus.data?.pin_enabled ?? false;
  const [mode, setMode] = useState<'password' | 'pin'>('password');

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

        {mode === 'pin' && pinEnabled ? (
          <PinLoginForm onUsePassword={() => setMode('password')} />
        ) : (
          <PasswordLoginForm
            showPinLink={pinEnabled}
            onUsePin={() => setMode('pin')}
          />
        )}
      </div>
    </div>
  );
}

function PasswordLoginForm({
  showPinLink,
  onUsePin,
}: {
  showPinLink: boolean;
  onUsePin: () => void;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const login = useLogin();
  const toast = useToast();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PasswordValues>({ resolver: zodResolver(passwordSchema) });

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
      {showPinLink && (
        <p className="text-center text-sm text-muted-foreground">
          <button
            type="button"
            onClick={onUsePin}
            className="font-medium text-primary underline-offset-4 hover:underline focus-ring rounded"
          >
            Sign in with PIN
          </button>
        </p>
      )}
    </form>
  );
}

function PinLoginForm({ onUsePassword }: { onUsePassword: () => void }) {
  const navigate = useNavigate();
  const location = useLocation();
  const pinLogin = usePinLogin();
  const toast = useToast();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PinValues>({ resolver: zodResolver(pinSchema) });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await pinLogin.mutateAsync({ pin: values.pin });
      const from = (location.state as { from?: string } | null)?.from || '/';
      navigate(from, { replace: true });
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : 'Sign in failed. Please try again.';
      toast.error('Could not sign in', message);
    }
  });

  return (
    <form
      onSubmit={onSubmit}
      className="space-y-4 rounded-lg border border-border bg-card p-6 shadow-sm"
    >
      <Field label="PIN" htmlFor="pin" required error={errors.pin?.message}>
        <Input
          id="pin"
          type="password"
          inputMode="numeric"
          autoComplete="off"
          pattern="\d{4,8}"
          maxLength={8}
          placeholder="••••"
          autoFocus
          className="h-12 text-center text-2xl tracking-[0.5em]"
          invalid={!!errors.pin}
          {...register('pin')}
        />
      </Field>
      <Button type="submit" className="w-full" loading={isSubmitting || pinLogin.isPending}>
        Sign in
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        <button
          type="button"
          onClick={onUsePassword}
          className="font-medium text-primary underline-offset-4 hover:underline focus-ring rounded"
        >
          Use password instead
        </button>
      </p>
    </form>
  );
}
