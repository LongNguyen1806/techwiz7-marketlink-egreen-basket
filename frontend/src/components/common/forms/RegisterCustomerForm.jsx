import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { Button } from '../../ui/Button';
import { FormAlert } from './FormAlert';
import { FormField } from './FormField';
import { useServerErrors } from './useServerErrors';
import { useAuth } from '../../../hooks/authentication/useAuth';
import { registerCustomerSchema } from '../../../services/common/auth.schemas';
import './RegisterForms.css';

const FIELDS = ['email', 'full_name', 'phone', 'address', 'password', 'confirm_password'];


export function RegisterCustomerForm() {
  const { registerCustomer, registerCustomerPending } = useAuth();
  const { formError, report, clear } = useServerErrors(FIELDS);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(registerCustomerSchema),
    defaultValues: {
      email: '', full_name: '', phone: '', address: '', password: '', confirm_password: '',
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    clear();
    try {
      await registerCustomer(values);
    } catch (error) {
      report(error, setError);
    }
  });

  return (
    <div className="register-form">
      <div>
        <p className="register-form__intro-eyebrow">Join as a shopper</p>
        <h1 className="register-form__title">Create your account</h1>
        <p className="register-form__subtitle">
          Reserve produce from local stalls and pick up when it suits you.
        </p>
        <Link to="/register/farmer" className="register-form__alt-link">
          Selling at a market? Register your stall
          <ArrowRight className="register-form__alt-link-icon" aria-hidden />
        </Link>
      </div>

      <form className="register-form__form" onSubmit={onSubmit} noValidate>
        <FormAlert message={formError} />

        <FormField
          id="register-full-name"
          label="Full name"
          autoComplete="name"
          error={errors.full_name?.message}
          {...register('full_name')}
        />
        <FormField
          id="register-email"
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register('email')}
        />
        <FormField
          id="register-phone"
          label="Phone number"
          type="tel"
          autoComplete="tel"
          error={errors.phone?.message}
          {...register('phone')}
        />
        <FormField
          id="register-address"
          label="Address"
          autoComplete="street-address"
          error={errors.address?.message}
          {...register('address')}
        />
        <FormField
          id="register-password"
          label="Password"
          type="password"
          autoComplete="new-password"
          error={errors.password?.message}
          {...register('password')}
        />
        <FormField
          id="register-confirm-password"
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          error={errors.confirm_password?.message}
          {...register('confirm_password')}
        />

        <Button
          type="submit"
          size="lg"
          className="register-form__submit"
          loading={registerCustomerPending}
        >
          Create my account
        </Button>
      </form>

      <p className="register-form__footer">
        Already shopping with us?{' '}
        <Link to="/login" className="register-form__footer-link">
          Sign in
        </Link>
      </p>
    </div>
  );
}
