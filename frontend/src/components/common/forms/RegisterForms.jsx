import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

import { Button } from '@/components/common/forms/Button';
import { Input } from '@/components/common/forms/Input';
import {
  registerCustomerSchema,
  registerFarmerSchema,
} from '../../../schemas/auth/auth.schemas';
import {
  useRegisterCustomer,
  useRegisterFarmer,
} from '../../../hooks/authentication/useAuth';
import { ApiError } from '@/lib/ApiError';
import { cn } from '@/lib/cn';
import { mapServerErrorsToForm } from '@/utils/mapServerErrors';

import './RegisterForms.css';

function AuthFooter({ prompt, linkTo, linkLabel }) {
  return (
    <p className="register-form__footer">
      {prompt}{' '}
      <Link to={linkTo} className="register-form__footer-link">
        {linkLabel}
      </Link>
    </p>
  );
}

export function RegisterCustomerForm() {
  const { mutateAsync: registerCustomer, isPending: registerCustomerPending } =
    useRegisterCustomer();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(registerCustomerSchema),
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
          <ArrowRight className="register-form__alt-link-icon" />
        </Link>
      </div>

      <form
        className="register-form__form"
        onSubmit={handleSubmit(async (values) => {
          try {
            await registerCustomer(values);
          } catch (error) {
            mapServerErrorsToForm(ApiError.fromUnknown(error).fieldErrors, setError);
          }
        })}
      >
        <div className="register-form__field">
          <Input id="full_name" label="Full name" {...register('full_name')} />
          {errors.full_name ? (
            <p className="register-form__error">{errors.full_name.message}</p>
          ) : null}
        </div>
        <div className="register-form__field">
          <Input id="email" type="email" label="Email" {...register('email')} />
          {errors.email ? (
            <p className="register-form__error">{errors.email.message}</p>
          ) : null}
        </div>
        <div className="register-form__field">
          <Input id="phone" label="Phone number" {...register('phone')} />
          {errors.phone ? (
            <p className="register-form__error">{errors.phone.message}</p>
          ) : null}
        </div>
        <div className="register-form__field">
          <Input id="address" label="Address" {...register('address')} />
          {errors.address ? (
            <p className="register-form__error">{errors.address.message}</p>
          ) : null}
        </div>
        <div className="register-form__field">
          <Input
            id="password"
            type="password"
            label="Password"
            {...register('password')}
          />
          {errors.password ? (
            <p className="register-form__error">{errors.password.message}</p>
          ) : null}
        </div>
        <div className="register-form__field">
          <Input
            id="confirm_password"
            type="password"
            label="Confirm password"
            {...register('confirm_password')}
          />
          {errors.confirm_password ? (
            <p className="register-form__error">{errors.confirm_password.message}</p>
          ) : null}
        </div>
        <Button
          type="submit"
          size="lg"
          className="register-form__submit"
          loading={registerCustomerPending}
        >
          Create my account
        </Button>
      </form>

      <AuthFooter
        prompt="Already shopping with us?"
        linkTo="/login"
        linkLabel="Sign in"
      />
    </div>
  );
}

export function RegisterFarmerForm() {
  const { mutateAsync: registerFarmer, isPending: registerFarmerPending } =
    useRegisterFarmer();
  const [step, setStep] = useState(1);
  const {
    register,
    handleSubmit,
    trigger,
    setError,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(registerFarmerSchema),
  });

  return (
    <div className="register-form">
      <div>
        <p className="register-form__intro-eyebrow">Join as a grower</p>
        <h1 className="register-form__title">Open your stall</h1>
        <p className="register-form__subtitle">
          Set up your profile — once approved, customers can pre-order from you on
          MarketLink.
        </p>
        <Link to="/register" className="register-form__alt-link">
          Looking to shop instead? Create a customer account
          <ArrowRight className="register-form__alt-link-icon" />
        </Link>
      </div>

      <div className="register-form__steps">
        <div className="register-form__steps-meta">
          <span>Step {step}/2</span>
          <span>{step === 1 ? 'Account details' : 'Stall details'}</span>
        </div>
        <div className="register-form__steps-bars">
          <div className={cn('register-form__steps-bar', step >= 1 && 'is-active')} />
          <div className={cn('register-form__steps-bar', step >= 2 && 'is-active')} />
        </div>
      </div>

      <form
        className="register-form__form"
        onSubmit={handleSubmit(async (values) => {
          try {
            await registerFarmer(values);
          } catch (error) {
            mapServerErrorsToForm(ApiError.fromUnknown(error).fieldErrors, setError);
          }
        })}
      >
        {step === 1 ? (
          <>
            <div className="register-form__field">
              <Input id="email" type="email" label="Email" {...register('email')} />
              {errors.email ? (
                <p className="register-form__error">{errors.email.message}</p>
              ) : null}
            </div>
            <div className="register-form__field">
              <Input id="phone" label="Phone number" {...register('phone')} />
              {errors.phone ? (
                <p className="register-form__error">{errors.phone.message}</p>
              ) : null}
            </div>
            <div className="register-form__field">
              <Input
                id="password"
                type="password"
                label="Password"
                {...register('password')}
              />
              {errors.password ? (
                <p className="register-form__error">{errors.password.message}</p>
              ) : null}
            </div>
            <div className="register-form__field">
              <Input
                id="confirm_password"
                type="password"
                label="Confirm password"
                {...register('confirm_password')}
              />
              {errors.confirm_password ? (
                <p className="register-form__error">{errors.confirm_password.message}</p>
              ) : null}
            </div>
            <Button
              type="button"
              size="lg"
              className="register-form__submit"
              onClick={async () => {
                const ok = await trigger([
                  'email',
                  'phone',
                  'password',
                  'confirm_password',
                ]);
                if (ok) setStep(2);
              }}
            >
              Continue
              <ArrowRight className="register-form__continue-icon" />
            </Button>
          </>
        ) : (
          <>
            <div className="register-form__field">
              <Input id="stall_name" label="Stall name" {...register('stall_name')} />
              {errors.stall_name ? (
                <p className="register-form__error">{errors.stall_name.message}</p>
              ) : null}
            </div>
            <div className="register-form__field">
              <Input
                id="contact_person"
                label="Contact person"
                {...register('contact_person')}
              />
              {errors.contact_person ? (
                <p className="register-form__error">{errors.contact_person.message}</p>
              ) : null}
            </div>
            <div className="register-form__field">
              <Input id="address" label="Address" {...register('address')} />
              {errors.address ? (
                <p className="register-form__error">{errors.address.message}</p>
              ) : null}
            </div>
            <div className="register-form__submit-row">
              <Button
                type="button"
                variant="outline"
                size="lg"
                className="register-form__submit"
                onClick={() => setStep(1)}
              >
                Back
              </Button>
              <Button
                type="submit"
                size="lg"
                className="register-form__submit"
                loading={registerFarmerPending}
              >
                Submit for review
              </Button>
            </div>
          </>
        )}
      </form>

      <AuthFooter
        prompt="Already have a stall account?"
        linkTo="/login"
        linkLabel="Sign in"
      />
    </div>
  );
}
