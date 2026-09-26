import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '../../ui/Button';
import { FormAlert } from './FormAlert';
import { FormField } from './FormField';
import { useServerErrors } from './useServerErrors';
import { useAuth } from '../../../hooks/authentication/useAuth';
import { changePasswordSchema } from '../../../services/common/auth.schemas';
import './ChangePasswordForm.css';

const FIELDS = ['current_password', 'new_password', 'confirm_password'];


export function ChangePasswordForm() {
  const { changePassword, changePasswordPending } = useAuth();
  const { formError, report, clear } = useServerErrors(FIELDS);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { current_password: '', new_password: '', confirm_password: '' },
  });

  const onSubmit = handleSubmit(async (values) => {
    clear();
    try {
      await changePassword(values);
      reset();
    } catch (error) {
      report(error, setError);
    }
  });

  return (
    <form className="change-password-form" onSubmit={onSubmit} noValidate>
      <FormAlert message={formError} />

      <FormField
        id="current-password"
        label="Current password"
        type="password"
        autoComplete="current-password"
        error={errors.current_password?.message}
        {...register('current_password')}
      />
      <FormField
        id="new-password"
        label="New password"
        type="password"
        autoComplete="new-password"
        error={errors.new_password?.message}
        {...register('new_password')}
      />
      <FormField
        id="confirm-new-password"
        label="Confirm new password"
        type="password"
        autoComplete="new-password"
        error={errors.confirm_password?.message}
        {...register('confirm_password')}
      />

      <Button type="submit" loading={changePasswordPending}>
        Change password
      </Button>
    </form>
  );
}
