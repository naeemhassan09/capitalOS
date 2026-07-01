import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { KeyRound } from 'lucide-react';
import { useSetupStatus, useSetPin, useRemovePin } from '@/api/auth';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/api/client';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Field } from '@/components/ui/Label';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';

const schema = z
  .object({
    current_password: z.string().min(1, 'Required'),
    pin: z.string().regex(/^\d{4,8}$/, 'PIN must be 4–8 digits'),
    confirm_pin: z.string(),
  })
  .refine((v) => v.pin === v.confirm_pin, {
    message: 'PINs do not match',
    path: ['confirm_pin'],
  });
type FormValues = z.infer<typeof schema>;

export function PinSection() {
  const setupStatus = useSetupStatus();
  const pinEnabled = setupStatus.data?.pin_enabled ?? false;

  const setPin = useSetPin();
  const removePin = useRemovePin();
  const toast = useToast();
  const [confirmRemove, setConfirmRemove] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await setPin.mutateAsync({ current_password: values.current_password, pin: values.pin });
      toast.success(pinEnabled ? 'PIN updated' : 'PIN set up');
      reset();
    } catch (err) {
      toast.error('Could not save PIN', err instanceof ApiError ? err.message : undefined);
    }
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="h-5 w-5 text-primary" /> PIN sign-in
          <Badge variant={pinEnabled ? 'success' : 'secondary'}>{pinEnabled ? 'On' : 'Off'}</Badge>
        </CardTitle>
        <CardDescription>
          {pinEnabled
            ? 'Sign in quickly with a numeric PIN. Change or remove it below.'
            : 'Set up a 4–8 digit PIN for quick sign-in. Your password is always still accepted.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={onSubmit} className="max-w-md space-y-4">
          <Field label="Current password" required error={errors.current_password?.message}>
            <Input type="password" autoComplete="current-password" {...register('current_password')} />
          </Field>
          <Field label={pinEnabled ? 'New PIN' : 'PIN'} required error={errors.pin?.message} hint="4–8 digits">
            <Input
              type="password"
              inputMode="numeric"
              autoComplete="off"
              pattern="\d{4,8}"
              maxLength={8}
              {...register('pin')}
            />
          </Field>
          <Field label="Confirm PIN" required error={errors.confirm_pin?.message}>
            <Input
              type="password"
              inputMode="numeric"
              autoComplete="off"
              pattern="\d{4,8}"
              maxLength={8}
              {...register('confirm_pin')}
            />
          </Field>
          <Button type="submit" loading={setPin.isPending}>
            {pinEnabled ? 'Change PIN' : 'Set up PIN'}
          </Button>
        </form>

        {pinEnabled && (
          <div className="border-t border-border pt-4">
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setConfirmRemove(true)}
              loading={removePin.isPending}
            >
              Remove PIN
            </Button>
          </div>
        )}
      </CardContent>

      <ConfirmDialog
        open={confirmRemove}
        onClose={() => setConfirmRemove(false)}
        title="Remove PIN?"
        description="PIN sign-in will be turned off. You can set it up again at any time."
        confirmLabel="Remove PIN"
        confirmVariant="destructive"
        loading={removePin.isPending}
        onConfirm={async () => {
          try {
            await removePin.mutateAsync();
            toast.success('PIN removed');
            setConfirmRemove(false);
          } catch (err) {
            toast.error('Could not remove PIN', err instanceof ApiError ? err.message : undefined);
          }
        }}
      />
    </Card>
  );
}
