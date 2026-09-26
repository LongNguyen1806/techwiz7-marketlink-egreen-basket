import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, CircleCheck } from 'lucide-react';
import { Button } from '../../ui/Button';
import { FormAlert } from './FormAlert';
import { FormField } from './FormField';
import { OperatingDaysField } from './OperatingDaysField';
import { useServerErrors } from './useServerErrors';
import { DASHBOARD_PATH } from '../../../constants';
import { useAuth } from '../../../hooks/authentication/useAuth';
import { registerFarmerSchema } from '../../../services/common/auth.schemas';
import { cn } from '../../../lib/cn';
import './RegisterForms.css';

const FIELDS = [
  'email', 'stall_name', 'contact_person', 'phone', 'address', 'operating_days',
  'password', 'confirm_password',
];
const STEP_ONE_FIELDS = ['email', 'phone', 'password', 'confirm_password'];

/**
 * G-11 (AU-02). Two steps: the account, then the stall. No coordinates are asked for — the backend
 * geocodes the address it is given (D-032).
 *
 * The stall is PENDING until an admin approves it (D-015), so a successful submission stays on an
 * approval notice rather than jumping to the Farmer workspace. The tokens AU-02 returns are held
 * until "Go to dashboard" is pressed: starting the session any earlier would make GuestOnlyRoute
 * redirect the page away before the notice could be read.
 */
export function RegisterFarmerForm() {
  const navigate = useNavigate();
  const { registerFarmer, registerFarmerPending, startSession } = useAuth();
  const { formError, report, clear } = useServerErrors(FIELDS);
  const [step, setStep] = useState(1);
  const [approved, setApproved] = useState(null);
  const {
    register,
    control,
    handleSubmit,
    trigger,
    setError,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(registerFarmerSchema),
    defaultValues: {
      email: '', stall_name: '', contact_person: '', phone: '', address: '',
      operating_days: [], password: '', confirm_password: '',
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    clear();
    try {
      setApproved(await registerFarmer(values));
    } catch (error) {
      report(error, setError);
    }
  });

  if (approved) {
    return (
      <div className="register-form">
        <div className="register-form__success">
          <span className="register-form__success-icon-wrap">
            <CircleCheck className="register-form__success-icon" strokeWidth={1.75} aria-hidden />
          </span>
          <h1 className="register-form__success-title">Registration successful</h1>
          <p className="register-form__success-text">
            Your account is awaiting administrator approval. Meanwhile, you can complete your stall
            profile.
          </p>
          <Button
            type="button"
            size="lg"
            onClick={() => {
              startSession(approved);
              navigate(DASHBOARD_PATH.FARMER, { replace: true });
            }}
          >
            Go to dashboard
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="register-form">
      <div>
        <p className="register-form__intro-eyebrow">Join as a grower</p>
        <h1 className="register-form__title">Open your stall</h1>
        <p className="register-form__subtitle">
          Set up your profile — once approved, customers can pre-order from you on MarketLink.
        </p>
        <Link to="/register" className="register-form__alt-link">
          Looking to shop instead? Create a customer account
          <ArrowRight className="register-form__alt-link-icon" aria-hidden />
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

      <form className="register-form__form" onSubmit={onSubmit} noValidate>
        <FormAlert message={formError} />

        {step === 1 ? (
          <>
            <FormField
              id="farmer-email"
              label="Email"
              type="email"
              autoComplete="email"
              error={errors.email?.message}
              {...register('email')}
            />
            <FormField
              id="farmer-phone"
              label="Phone number"
              type="tel"
              autoComplete="tel"
              error={errors.phone?.message}
              {...register('phone')}
            />
            <FormField
              id="farmer-password"
              label="Password"
              type="password"
              autoComplete="new-password"
              error={errors.password?.message}
              {...register('password')}
            />
            <FormField
              id="farmer-confirm-password"
              label="Confirm password"
              type="password"
              autoComplete="new-password"
              error={errors.confirm_password?.message}
              {...register('confirm_password')}
            />
            <Button
              type="button"
              size="lg"
              className="register-form__submit"
              onClick={async () => {
                if (await trigger(STEP_ONE_FIELDS)) setStep(2);
              }}
            >
              Continue
              <ArrowRight className="register-form__continue-icon" aria-hidden />
            </Button>
          </>
        ) : (
          <>
            <FormField
              id="farmer-stall-name"
              label="Stall name"
              autoComplete="organization"
              error={errors.stall_name?.message}
              {...register('stall_name')}
            />
            <FormField
              id="farmer-contact-person"
              label="Contact person"
              autoComplete="name"
              error={errors.contact_person?.message}
              {...register('contact_person')}
            />
            <FormField
              id="farmer-address"
              label="Address"
              autoComplete="street-address"
              error={errors.address?.message}
              {...register('address')}
            />

            <Controller
              name="operating_days"
              control={control}
              render={({ field }) => (
                <OperatingDaysField
                  id="farmer-operating-days"
                  value={field.value}
                  onChange={field.onChange}
                  error={errors.operating_days?.message}
                  hint="The days your stall is open. You can change them later on your profile."
                />
              )}
            />

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

      <p className="register-form__footer">
        Already have a stall account?{' '}
        <Link to="/login" className="register-form__footer-link">
          Sign in
        </Link>
      </p>
    </div>
  );
}
