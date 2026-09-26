import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link } from 'react-router-dom';
import { ArrowRight, Store, UserRound } from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { ROUTES } from '../../constants/routes';
import { useLogin } from '../../hooks/authentication/useAuth';
import { ApiError } from '../../lib/ApiError';
import { loginSchema } from '../../schemas/common/auth.schema';
import { mapServerErrorsToForm } from '../../utils/mapServerErrors';
import '../../styles/auth/LoginForm.css';

// Accounts created by `python manage.py seed_minimal` with its local-only default password.
// Shown in development builds only. Admins sign in through their own portal.
const DEMO_ACCOUNTS = import.meta.env.DEV
  ? [
      { email: 'customer@marketlink.local', label: 'Customer', password: 'Demo@12345', icon: UserRound },
      { email: 'farmer1@marketlink.local', label: 'Farmer', password: 'Demo@12345', icon: Store },
    ]
  : [];

const LOGIN_FIELDS = ['email', 'password'];

export function LoginForm() {
  const login = useLogin();
  const {
    register,
    handleSubmit,
    setValue,
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

  const signInAs = (account) => {
    setValue('email', account.email);
    setValue('password', account.password);
    void onSubmit();
  };

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

      {DEMO_ACCOUNTS.length > 0 ? (
        <div className="login-form__demo">
          <div className="login-form__demo-divider">
            <span className="login-form__demo-line" />
            <p className="login-form__demo-label">Try a demo account</p>
            <span className="login-form__demo-line" />
          </div>
          <div className="login-form__demo-list">
            {DEMO_ACCOUNTS.map((account) => {
              const Icon = account.icon;
              return (
                <button
                  key={account.email}
                  type="button"
                  disabled={login.isPending}
                  onClick={() => signInAs(account)}
                  className="login-form__demo-btn"
                >
                  <span className="login-form__demo-icon-wrap">
                    <Icon className="login-form__demo-icon" strokeWidth={1.75} />
                  </span>
                  <span className="login-form__demo-text">
                    <span className="login-form__demo-role">{account.label}</span>
                    <span className="login-form__demo-email">{account.email}</span>
                  </span>
                  <ArrowRight className="login-form__demo-arrow" />
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

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
