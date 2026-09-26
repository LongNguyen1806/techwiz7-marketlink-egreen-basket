import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { FormAlert } from '../../components/common/forms/FormAlert';
import { FormField } from '../../components/common/forms/FormField';
import { useServerErrors } from '../../components/common/forms/useServerErrors';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Button } from '../../components/ui/Button';
import { useCustomerProfile, useUpdateCustomerProfile } from '../../hooks/queries/customer/useCustomerProfile';
import { profileSchema } from '../../services/customer/profile.schemas';
import '../../styles/customer/ProfilePage.css';

const FIELDS = ['full_name', 'phone', 'address'];


export default function ProfilePage() {
  const { data: profile, isLoading } = useCustomerProfile();
  const update = useUpdateCustomerProfile();
  const { formError, report, clear } = useServerErrors(FIELDS);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, dirtyFields, isDirty },
  } = useForm({
    resolver: zodResolver(profileSchema),
    defaultValues: { full_name: '', phone: '', address: '' },
  });

  useEffect(() => {
    if (profile) reset({ full_name: profile.full_name, phone: profile.phone, address: profile.address });
  }, [profile, reset]);

  const onSubmit = handleSubmit(async (values) => {
    clear();
    
    const changed = Object.fromEntries(
      Object.keys(values).filter((field) => dirtyFields[field]).map((field) => [field, values[field]]),
    );
    if (Object.keys(changed).length === 0) return;
    try {
      const saved = await update.mutateAsync(changed);
      reset({ full_name: saved.full_name, phone: saved.phone, address: saved.address });
    } catch (error) {
      report(error, setError);
    }
  });

  if (isLoading) return <PageSkeleton />;

  return (
    <section className="profile-page">
      <PageHeader title="My profile" description="Used on your orders so the stall knows who to hand them to." />

      <form className="profile-page__form" onSubmit={onSubmit} noValidate>
        <FormAlert message={formError} />

        <FormField
          id="profile-full-name"
          label="Full name"
          autoComplete="name"
          error={errors.full_name?.message}
          {...register('full_name')}
        />
        <FormField
          id="profile-phone"
          label="Phone number"
          type="tel"
          autoComplete="tel"
          error={errors.phone?.message}
          {...register('phone')}
        />
        <FormField
          id="profile-address"
          label="Address"
          autoComplete="street-address"
          error={errors.address?.message}
          {...register('address')}
        />
        <FormField
          id="profile-email"
          label="Email"
          type="email"
          value={profile?.email ?? ''}
          readOnly
          disabled
        />

        <Button type="submit" loading={update.isPending} disabled={!isDirty}>
          Save
        </Button>
      </form>
    </section>
  );
}
