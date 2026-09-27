import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link } from 'react-router-dom';
import { ArrowRight, ShieldCheck, Store, UserRound } from 'lucide-react';

import { Button } from '@/components/common/forms/Button';
import { Input } from '@/components/common/forms/Input';
import { useLogin } from '../../../hooks/authentication/useAuth';
import { loginSchema } from '../../../schemas/auth/auth.schemas';
import { ApiError } from '@/lib/ApiError';
import { mapServerErrorsToForm } from '@/utils/mapServerErrors';

import './LoginForm.css';

// The accounts the seed command creates (manage.py seed_minimal). Admin is not among them:
// D-027 keeps the two portals apart, so this page refuses an admin the same way it refuses a
// wrong password, and the shortcut below sends them to /admin/login instead.
const DEMO_ACCOUNTS = [
  {
    email: 'customer@marketlink.local',
    label: 'Customer',
    password: 'Demo@12345',
    icon: UserRound,
  },
  {
    email: 'farmer1@marketlink.local',
    label: 'Farmer',
    password: 'Demo@12345',
    icon: Store,
  },
];

export function LoginForm() {
  const { mutateAsync: login, isPending: loginPending } = useLogin();
  const pending = loginPending;
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

  const submitLogin = async (values) => {
    try {
      await login(values);
    } catch (error) {
      const apiError = ApiError.fromUnknown(error);
      mapServerErrorsToForm(apiError.fieldErrors, setError);
    }
  };

  return (
    <div className="login-form">
      <div>
        <p className="login-form__intro-eyebrow">Welcome back</p>
        <h1 className="login-form__title">Sign in to MarketLink</h1>
        <p className="login-form__subtitle">
          Pick up where you left off — browse stalls, reserve produce, and collect on your
          schedule.
        </p>
      </div>

      <form
        className="login-form__form"
        onSubmit={handleSubmit(async (values) => {
          await submitLogin(values);
        })}
      >
        <div className="login-form__field">
          <Input
            id="email"
            type="email"
            label="Email"
            autoComplete="email"
            {...register('email')}
          />
          {errors.email ? (
            <p className="login-form__error">{errors.email.message}</p>
          ) : null}
        </div>
        <div className="login-form__field">
          <Input
            id="password"
            type="password"
            label="Password"
            autoComplete="current-password"
            {...register('password')}
          />
          {errors.password ? (
            <p className="login-form__error">{errors.password.message}</p>
          ) : null}
        </div>
        <Button type="submit" size="lg" className="login-form__submit" loading={pending}>
          Sign in
        </Button>
      </form>

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
                disabled={pending}
                onClick={() => {
                  setValue('email', account.email);
                  setValue('password', account.password);
                  void submitLogin({
                    email: account.email,
                    password: account.password,
                  });
                }}
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
          <Link to="/admin/login" className="login-form__demo-btn">
            <span className="login-form__demo-icon-wrap">
              <ShieldCheck className="login-form__demo-icon" strokeWidth={1.75} />
            </span>
            <span className="login-form__demo-text">
              <span className="login-form__demo-role">Admin</span>
              <span className="login-form__demo-email">Sign in at the admin portal</span>
            </span>
            <ArrowRight className="login-form__demo-arrow" />
          </Link>
        </div>
      </div>

      <div className="login-form__footer">
        <p>New to MarketLink?</p>
        <div className="login-form__footer-links">
          <Link to="/register" className="login-form__footer-link">
            Shop as a customer
            <ArrowRight className="login-form__footer-link-icon" />
          </Link>
          <span className="login-form__footer-sep" aria-hidden>
            |
          </span>
          <Link to="/register/farmer" className="login-form__footer-link">
            Sell as a farmer
            <ArrowRight className="login-form__footer-link-icon" />
          </Link>
        </div>
      </div>
    </div>
  );
}
