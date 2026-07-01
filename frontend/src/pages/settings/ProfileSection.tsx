import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useChangePassword } from '@/api/auth';
import { useAuth } from '@/routes/AuthContext';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Field } from '@/components/ui/Label';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';

export function ProfileSection() {
  const { user } = useAuth();
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Your account details.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Row label="Display name" value={user.display_name} />
          <Row label="Email" value={user.email} />
          <Row label="Base currency" value={user.base_currency} />
          <Row label="Timezone" value={user.timezone} />
          <Row
            label="Role"
            value={<Badge variant={user.is_owner ? 'default' : 'secondary'}>{user.is_owner ? 'Owner' : 'Member'}</Badge>}
          />
          <Row
            label="Two-factor"
            value={<Badge variant={user.totp_enabled ? 'success' : 'secondary'}>{user.totp_enabled ? 'Enabled' : 'Disabled'}</Badge>}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-border pb-3 last:border-0 last:pb-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-foreground">{value}</span>
    </div>
  );
}

const schema = z
  .object({
    current_password: z.string().min(1, 'Required'),
    new_password: z.string().min(8, 'Use at least 8 characters'),
    confirm_password: z.string(),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });
type FormValues = z.infer<typeof schema>;

export function ChangePasswordSection() {
  const change = useChangePassword();
  const toast = useToast();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await change.mutateAsync({ current_password: values.current_password, new_password: values.new_password });
      toast.success('Password changed');
      reset();
    } catch (err) {
      toast.error('Could not change password', err instanceof ApiError ? err.message : undefined);
    }
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Change password</CardTitle>
        <CardDescription>Use a strong, unique password.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="max-w-md space-y-4">
          <Field label="Current password" required error={errors.current_password?.message}>
            <Input type="password" autoComplete="current-password" {...register('current_password')} />
          </Field>
          <Field label="New password" required error={errors.new_password?.message}>
            <Input type="password" autoComplete="new-password" {...register('new_password')} />
          </Field>
          <Field label="Confirm new password" required error={errors.confirm_password?.message}>
            <Input type="password" autoComplete="new-password" {...register('confirm_password')} />
          </Field>
          <Button type="submit" loading={change.isPending}>
            Update password
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
