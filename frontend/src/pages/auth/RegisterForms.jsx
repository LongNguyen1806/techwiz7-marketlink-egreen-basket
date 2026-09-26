import { useState } from 'react';
import PropTypes from 'prop-types';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Label } from '../../components/ui/Label';
import { ROUTES } from '../../constants/routes';
import { useRegisterCustomer, useRegisterFarmer } from '../../hooks/authentication/useAuth';
import { ApiError } from '../../lib/ApiError';
import { cn } from '../../lib/cn';
import {
  REGISTER_FARMER_STEP_1,
  registerCustomerSchema,
  registerFarmerSchema,
} from '../../schemas/common/auth.schema';
import { DAYS_OF_WEEK } from '../../utils/labels';
import { mapServerErrorsToForm } from '../../utils/mapServerErrors';
import '../../styles/auth/RegisterForms.css';

const CUSTOMER_DEFAULTS = {
  full_name: '',
  email: '',
  phone: '',
  address: '',
  password: '',
  confirm_password: '',
};

const FARMER_DEFAULTS = {
  email: '',
  phone: '',
  password: '',
  confirm_password: '',
  stall_name: '',
  contact_person: '',
  address: '',
  operating_days: [],
};

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

AuthFooter.propTypes = {
  prompt: PropTypes.string.isRequired,
  linkTo: PropTypes.string.isRequired,
  linkLabel: PropTypes.string.isRequired,
};

function FieldError({ error }) {
  return error ? <p className="register-form__error">{error.message}</p> : null;
}

FieldError.propTypes = {
  error: PropTypes.shape({ message: PropTypes.string }),
};

export function RegisterCustomerForm() {
  const registerCustomer = useRegisterCustomer();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(registerCustomerSchema),
    defaultValues: CUSTOMER_DEFAULTS,
  });

  const onSubmit = handleSubmit((values) =>
    registerCustomer.mutate(values, {
      onError: (error) =>
        mapServerErrorsToForm(ApiError.fromUnknown(error).fieldErrors, setError, {
          fields: Object.keys(CUSTOMER_DEFAULTS),
        }),
    }),
  );

  return (
    <div className="register-form">
      <div>
        <p className="register-form__intro-eyebrow">Join as a shopper</p>
        <h1 className="register-form__title">Create your account</h1>
        <p className="register-form__subtitle">Reserve produce from local stalls and pick up when it suits you.</p>
        <Link to={ROUTES.REGISTER_FARMER} className="register-form__alt-link">
          Selling at a market? Register your stall
          <ArrowRight className="register-form__alt-link-icon" />
        </Link>
      </div>

      <form className="register-form__form" onSubmit={onSubmit} noValidate>
        <div className="register-form__field">
          <Input id="full_name" label="Full name" autoComplete="name" {...register('full_name')} />
          <FieldError error={errors.full_name} />
        </div>
        <div className="register-form__field">
          <Input id="email" type="email" label="Email" autoComplete="email" {...register('email')} />
          <FieldError error={errors.email} />
        </div>
        <div className="register-form__field">
          <Input id="phone" type="tel" label="Phone number" autoComplete="tel" {...register('phone')} />
          <FieldError error={errors.phone} />
        </div>
        <div className="register-form__field">
          <Input id="address" label="Address" autoComplete="street-address" {...register('address')} />
          <FieldError error={errors.address} />
        </div>
        <div className="register-form__field">
          <Input id="password" type="password" label="Password" autoComplete="new-password" {...register('password')} />
          <FieldError error={errors.password} />
        </div>
        <div className="register-form__field">
          <Input
            id="confirm_password"
            type="password"
            label="Confirm password"
            autoComplete="new-password"
            {...register('confirm_password')}
          />
          <FieldError error={errors.confirm_password} />
        </div>
        <FieldError error={errors.root?.server} />
        <Button type="submit" size="lg" className="register-form__submit" loading={registerCustomer.isPending}>
          Create my account
        </Button>
      </form>

      <AuthFooter prompt="Already shopping with us?" linkTo={ROUTES.LOGIN} linkLabel="Sign in" />
    </div>
  );
}

function OperatingDaysPicker({ value, onChange, onBlur }) {
  const toggle = (day) => {
    const next = value.includes(day) ? value.filter((d) => d !== day) : [...value, day];
    onChange(next.sort((a, b) => a - b));
  };

  return (
    <div className="page-primitive__actions-row" role="group" aria-label="Operating days">
      {DAYS_OF_WEEK.map((day) => {
        const selected = value.includes(day.value);
        return (
          <Button
            key={day.value}
            type="button"
            size="sm"
            variant={selected ? 'default' : 'outline'}
            aria-pressed={selected}
            aria-label={day.long}
            onClick={() => toggle(day.value)}
            onBlur={onBlur}
          >
            {day.short}
          </Button>
        );
      })}
    </div>
  );
}

OperatingDaysPicker.propTypes = {
  value: PropTypes.arrayOf(PropTypes.number).isRequired,
  onChange: PropTypes.func.isRequired,
  onBlur: PropTypes.func,
};

export function RegisterFarmerForm() {
  const registerFarmer = useRegisterFarmer();
  const [step, setStep] = useState(1);
  const {
    register,
    control,
    handleSubmit,
    trigger,
    setError,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(registerFarmerSchema),
    defaultValues: FARMER_DEFAULTS,
  });

  const goToStep2 = async () => {
    if (await trigger(REGISTER_FARMER_STEP_1, { shouldFocus: true })) setStep(2);
  };

  const onSubmit = handleSubmit((values) =>
    registerFarmer.mutate(values, {
      onError: (error) => {
        const { fieldErrors } = ApiError.fromUnknown(error);
        mapServerErrorsToForm(fieldErrors, setError, { fields: Object.keys(FARMER_DEFAULTS) });
        
        if (REGISTER_FARMER_STEP_1.some((field) => fieldErrors[field])) setStep(1);
      },
    }),
  );

  return (
    <div className="register-form">
      <div>
        <p className="register-form__intro-eyebrow">Join as a grower</p>
        <h1 className="register-form__title">Open your stall</h1>
        <p className="register-form__subtitle">
          Set up your profile — once approved, customers can pre-order from you on MarketLink.
        </p>
        <Link to={ROUTES.REGISTER_CUSTOMER} className="register-form__alt-link">
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

      <form className="register-form__form" onSubmit={onSubmit} noValidate>
        {step === 1 ? (
          <>
            <div className="register-form__field">
              <Input id="email" type="email" label="Email" autoComplete="email" {...register('email')} />
              <FieldError error={errors.email} />
            </div>
            <div className="register-form__field">
              <Input id="phone" type="tel" label="Phone number" autoComplete="tel" {...register('phone')} />
              <FieldError error={errors.phone} />
            </div>
            <div className="register-form__field">
              <Input
                id="password"
                type="password"
                label="Password"
                autoComplete="new-password"
                {...register('password')}
              />
              <FieldError error={errors.password} />
            </div>
            <div className="register-form__field">
              <Input
                id="confirm_password"
                type="password"
                label="Confirm password"
                autoComplete="new-password"
                {...register('confirm_password')}
              />
              <FieldError error={errors.confirm_password} />
            </div>
            <Button type="button" size="lg" className="register-form__submit" onClick={goToStep2}>
              Continue
              <ArrowRight className="register-form__continue-icon" />
            </Button>
          </>
        ) : (
          <>
            <div className="register-form__field">
              <Input id="stall_name" label="Stall name" autoComplete="organization" {...register('stall_name')} />
              <FieldError error={errors.stall_name} />
            </div>
            <div className="register-form__field">
              <Input id="contact_person" label="Contact person" autoComplete="name" {...register('contact_person')} />
              <FieldError error={errors.contact_person} />
            </div>
            <div className="register-form__field">
              <Input id="address" label="Address" autoComplete="street-address" {...register('address')} />
              <FieldError error={errors.address} />
            </div>
            <div className="register-form__field">
              <Label>Operating days</Label>
              <Controller
                control={control}
                name="operating_days"
                render={({ field }) => (
                  <OperatingDaysPicker value={field.value} onChange={field.onChange} onBlur={field.onBlur} />
                )}
              />
              <FieldError error={errors.operating_days} />
            </div>
            <FieldError error={errors.root?.server} />
            <div className="register-form__submit-row">
              <Button type="button" variant="outline" size="lg" className="register-form__submit" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button type="submit" size="lg" className="register-form__submit" loading={registerFarmer.isPending}>
                Submit for review
              </Button>
            </div>
          </>
        )}
      </form>

      <AuthFooter prompt="Already have a stall account?" linkTo={ROUTES.LOGIN} linkLabel="Sign in" />
    </div>
  );
}
