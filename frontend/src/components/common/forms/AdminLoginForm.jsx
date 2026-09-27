import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useLocation, useNavigate } from 'react-router-dom';
import { ShieldCheck } from 'lucide-react';

import { Button } from '@/components/common/forms/Button';
import { Input } from '@/components/common/forms/Input';
import { DASHBOARD_PATH } from '@/config/constants';
import { useAdminLogin } from '../../../hooks/authentication/useAuth';
import { loginSchema } from '../../../schemas/auth/auth.schemas';
import { ApiError } from '@/lib/ApiError';
import { mapServerErrorsToForm } from '@/utils/mapServerErrors';

import './AdminLoginForm.css';

// Only a path inside the admin area may be resumed after signing in, so a crafted "from"
// cannot bounce an admin somewhere else.
function resumePath(from) {
  if (typeof from !== 'object' || from === null) return null;
  const pathname = from.pathname;
  if (typeof pathname !== 'string') return null;
  if (!pathname.startsWith(`${DASHBOARD_PATH.ADMIN}/`)) return null;
  return pathname === '/admin/login' ? null : pathname;
}

// A-00 (D-027). No register or password-reset link: admin accounts are issued by IT, and a
// wrong portal reads exactly like a wrong password so nobody can probe for admin emails.
export function AdminLoginForm() {
  const { mutateAsync: adminLogin, isPending: adminLoginPending } = useAdminLogin();
  const navigate = useNavigate();
  const location = useLocation();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  });

  return (
    <div className="admin-login-form">
      <span className="admin-login-form__badge">
        <ShieldCheck className="admin-login-form__badge-icon" strokeWidth={1.75} />
      </span>

      <div>
        <p className="admin-login-form__eyebrow">Staff access</p>
        <h1 className="admin-login-form__title">Admin portal</h1>
        <p className="admin-login-form__subtitle">
          Sign in with the account your IT team issued you.
        </p>
      </div>

      <form
        className="admin-login-form__form"
        onSubmit={handleSubmit(async (values) => {
          try {
            await adminLogin(values);
            // useAdminLogin already sent us to /admin; go deeper only if that is where we came from.
            const resume = resumePath(location.state?.from);
            if (resume) navigate(resume, { replace: true });
          } catch (error) {
            mapServerErrorsToForm(ApiError.fromUnknown(error).fieldErrors, setError);
          }
        })}
      >
        <div className="admin-login-form__field">
          <Input
            id="admin-email"
            type="email"
            label="Email"
            autoComplete="email"
            {...register('email')}
          />
          {errors.email ? (
            <p className="admin-login-form__error">{errors.email.message}</p>
          ) : null}
        </div>
        <div className="admin-login-form__field">
          <Input
            id="admin-password"
            type="password"
            label="Password"
            autoComplete="current-password"
            {...register('password')}
          />
          {errors.password ? (
            <p className="admin-login-form__error">{errors.password.message}</p>
          ) : null}
        </div>
        <Button
          type="submit"
          size="lg"
          className="admin-login-form__submit"
          loading={adminLoginPending}
        >
          Sign in
        </Button>
      </form>

      <p className="admin-login-form__note">
        Shoppers and farmers sign in on the main page.
      </p>
    </div>
  );
}
