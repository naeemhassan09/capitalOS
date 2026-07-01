import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ShieldCheck } from 'lucide-react';
import { useSetup } from '@/api/auth';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { SUPPORTED_CURRENCIES } from '@/utils/money';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Field } from '@/components/ui/Label';
import { ThemeToggle } from '@/components/ui/ThemeToggle';

const TIMEZONES = [
  'Europe/Dublin',
  'Asia/Karachi',
  'Europe/London',
  'Asia/Riyadh',
  'America/New_York',
  'UTC',
];

const schema = z
  .object({
    display_name: z.string().min(1, 'Your name is required'),
    email: z.string().email('Enter a valid email'),
    password: z.string().min(8, 'Use at least 8 characters'),
    confirm_password: z.string(),
    base_currency: z.enum(['EUR', 'PKR', 'USD', 'GBP', 'SAR']),
    timezone: z.string().min(1, 'Select a timezone'),
  })
  .refine((v) => v.password === v.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

type FormValues = z.infer<typeof schema>;

export function SetupPage() {
  const navigate = useNavigate();
  const setup = useSetup();
  const toast = useToast();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { base_currency: 'EUR', timezone: 'Europe/Dublin' },
  });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await setup.mutateAsync({
        email: values.email,
        password: values.password,
        display_name: values.display_name,
        base_currency: values.base_currency,
        timezone: values.timezone,
      });
      toast.success('Welcome to CapitalOS', 'Your owner account is ready.');
      navigate('/', { replace: true });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Setup failed. Please try again.';
      toast.error('Could not complete setup', message);
    }
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>
      <div className="w-full max-w-md">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <ShieldCheck className="h-6 w-6" aria-hidden />
          </span>
          <h1 className="text-2xl font-semibold text-foreground">Set up CapitalOS</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Create the owner account for your private finance workspace.
          </p>
        </div>

        <form
          onSubmit={onSubmit}
          className="space-y-4 rounded-lg border border-border bg-card p-6 shadow-sm"
        >
          <Field label="Display name" htmlFor="display_name" required error={errors.display_name?.message}>
            <Input id="display_name" autoComplete="name" invalid={!!errors.display_name} {...register('display_name')} />
          </Field>

          <Field label="Email" htmlFor="email" required error={errors.email?.message}>
            <Input id="email" type="email" autoComplete="email" invalid={!!errors.email} {...register('email')} />
          </Field>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Password" htmlFor="password" required error={errors.password?.message}>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                invalid={!!errors.password}
                {...register('password')}
              />
            </Field>
            <Field
              label="Confirm password"
              htmlFor="confirm_password"
              required
              error={errors.confirm_password?.message}
            >
              <Input
                id="confirm_password"
                type="password"
                autoComplete="new-password"
                invalid={!!errors.confirm_password}
                {...register('confirm_password')}
              />
            </Field>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Base currency" htmlFor="base_currency" required error={errors.base_currency?.message}>
              <Select id="base_currency" invalid={!!errors.base_currency} {...register('base_currency')}>
                {SUPPORTED_CURRENCIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Timezone" htmlFor="timezone" required error={errors.timezone?.message}>
              <Select id="timezone" invalid={!!errors.timezone} {...register('timezone')}>
                {TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>
                    {tz}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          <Button type="submit" className="w-full" loading={isSubmitting || setup.isPending}>
            Create account
          </Button>
        </form>
      </div>
    </div>
  );
}
