import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { Button } from '../../ui/Button';
import { FormAlert } from './FormAlert';
import { FormField } from './FormField';
import { useServerErrors } from './useServerErrors';
import { useAuth } from '../../../hooks/authentication/useAuth';
import { loginSchema } from '../../../services/common/auth.schemas';
import './LoginForm.css';

const FIELDS = ['email', 'password'];


export function LoginForm() {
  const { login, loginPending } = useAuth();
  const { formError, report, clear } = useServerErrors(FIELDS);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  });

  const onSubmit = handleSubmit(async (values) => {
    clear();
    try {
      await login(values);
    } catch (error) {
      report(error, setError);
    }
  });

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
        <FormAlert message={formError} />

        <FormField
          id="login-email"
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register('email')}
        />
        <FormField
          id="login-password"
          label="Password"
          type="password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...register('password')}
        />

        <Button type="submit" size="lg" className="login-form__submit" loading={loginPending}>
          Sign in
        </Button>
      </form>

      <div className="login-form__footer">
        <p>New to MarketLink?</p>
        <div className="login-form__footer-links">
          <Link to="/register" className="login-form__footer-link">
            Sign up as a customer
            <ArrowRight className="login-form__footer-link-icon" aria-hidden />
          </Link>
          <span className="login-form__footer-sep" aria-hidden>
            |
          </span>
          <Link to="/register/farmer" className="login-form__footer-link">
            Sign up as a seller (Farmer)
            <ArrowRight className="login-form__footer-link-icon" aria-hidden />
          </Link>
        </div>
      </div>
    </div>
  );
}
