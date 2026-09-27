import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { ROUTES } from '../../constants/routes';
import { useLogin } from '../../hooks/authentication/useAuth';
import { ApiError } from '../../lib/ApiError';
import { loginSchema } from '../../schemas/common/auth.schema';
import { mapServerErrorsToForm } from '../../utils/mapServerErrors';
import '../../styles/auth/LoginForm.css';

const LOGIN_FIELDS = ['email', 'password'];

export function LoginForm() {
  const login = useLogin();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  });

  const onSubmit = handleSubmit((values) =>
    login.mutate(values, {
      onError: (error) => mapServerErrorsToForm(ApiError.fromUnknown(error).fieldErrors, setError, { fields: LOGIN_FIELDS }),
    }),
  );

  return (
    <div className="login-form">
      <div>
        <p className="login-form__intro-eyebrow">Welcome back</p>
        <h1 className="login-form__title">Sign in to MarketLink</h1>
        <p className="login-form__subtitle">
          Pick up where you left off — browse stalls, reserve produce, and collect on your schedule.
        </p>
      </div>

      <form className="login-form__form" onSubmit={onSubmit} noValidate>
        <div className="login-form__field">
          <Input id="email" type="email" label="Email" autoComplete="email" {...register('email')} />
          {errors.email ? <p className="login-form__error">{errors.email.message}</p> : null}
        </div>
        <div className="login-form__field">
          <Input
            id="password"
            type="password"
            label="Password"
            autoComplete="current-password"
            {...register('password')}
          />
          {errors.password ? <p className="login-form__error">{errors.password.message}</p> : null}
        </div>
        {errors.root?.server ? <p className="login-form__error">{errors.root.server.message}</p> : null}
        <Button type="submit" size="lg" className="login-form__submit" loading={login.isPending}>
          Sign in
        </Button>
      </form>

      <div className="login-form__footer">
        <p>New to MarketLink?</p>
        <div className="login-form__footer-links">
          <Link to={ROUTES.REGISTER_CUSTOMER} className="login-form__footer-link">
            Shop as a customer
            <ArrowRight className="login-form__footer-link-icon" />
          </Link>
          <span className="login-form__footer-sep" aria-hidden>
            |
          </span>
          <Link to={ROUTES.REGISTER_FARMER} className="login-form__footer-link">
            Sell as a farmer
            <ArrowRight className="login-form__footer-link-icon" />
          </Link>
        </div>
      </div>
    </div>
  );
}
