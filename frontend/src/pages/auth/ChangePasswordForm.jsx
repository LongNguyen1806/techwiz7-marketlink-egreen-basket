import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { useChangePassword } from '../../hooks/authentication/useAuth';
import { ApiError } from '../../lib/ApiError';
import { changePasswordSchema } from '../../schemas/common/auth.schema';
import { mapServerErrorsToForm } from '../../utils/mapServerErrors';
import '../../styles/auth/ChangePasswordForm.css';

const DEFAULTS = { current_password: '', new_password: '', confirm_password: '' };

export function ChangePasswordForm() {
  const changePassword = useChangePassword();
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isDirty },
  } = useForm({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: DEFAULTS,
  });

  const onSubmit = handleSubmit((values) =>
    changePassword.mutate(values, {
      onSuccess: () => reset(DEFAULTS),
      onError: (error) =>
        mapServerErrorsToForm(ApiError.fromUnknown(error).fieldErrors, setError, { fields: Object.keys(DEFAULTS) }),
    }),
  );

  return (
    <form className="change-password-form" onSubmit={onSubmit} noValidate>
      <div className="change-password-form__field">
        <Input
          id="current_password"
          type="password"
          label="Current password"
          autoComplete="current-password"
          {...register('current_password')}
        />
        {errors.current_password ? (
          <p className="change-password-form__error">{errors.current_password.message}</p>
        ) : null}
      </div>
      <div className="change-password-form__field">
        <Input
          id="new_password"
          type="password"
          label="New password"
          autoComplete="new-password"
          {...register('new_password')}
        />
        {errors.new_password ? <p className="change-password-form__error">{errors.new_password.message}</p> : null}
      </div>
      <div className="change-password-form__field">
        <Input
          id="confirm_password"
          type="password"
          label="Confirm new password"
          autoComplete="new-password"
          {...register('confirm_password')}
        />
        {errors.confirm_password ? (
          <p className="change-password-form__error">{errors.confirm_password.message}</p>
        ) : null}
      </div>
      {errors.root?.server ? <p className="change-password-form__error">{errors.root.server.message}</p> : null}
      <Button type="submit" loading={changePassword.isPending} disabled={!isDirty}>
        Change password
      </Button>
    </form>
  );
}
