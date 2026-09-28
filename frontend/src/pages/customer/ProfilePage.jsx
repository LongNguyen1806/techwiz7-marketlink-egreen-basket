import { useEffect, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { FormAlert } from '../../components/common/forms/FormAlert';
import { FormField } from '../../components/common/forms/FormField';
import { useServerErrors } from '../../components/common/forms/useServerErrors';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/Avatar';
import { Button } from '../../components/ui/Button';
import { useObjectUrl } from '../../hooks/common/useObjectUrl';
import { useCustomerProfile, useUpdateCustomerProfile } from '../../hooks/queries/customer/useCustomerProfile';
import { IMAGE_TYPES } from '../../schemas/farmer/product.schema';
import { profileSchema } from '../../services/customer/profile.schemas';
import '../../styles/customer/ProfilePage.css';

const FIELDS = ['full_name', 'phone', 'address', 'image'];
const TEXT_FIELDS = ['full_name', 'phone', 'address'];

const toFormValues = (profile) => ({
  full_name: profile.full_name,
  phone: profile.phone,
  address: profile.address,
  image: null,
  remove_image: false,
});

function initials(name, email) {
  const parts = (name ?? '').trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return (email ?? '?').charAt(0).toUpperCase();
}


export default function ProfilePage() {
  const { data: profile, isLoading } = useCustomerProfile();
  const update = useUpdateCustomerProfile();
  const { formError, report, clear } = useServerErrors(FIELDS);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    setValue,
    watch,
    formState: { errors, dirtyFields, isDirty },
  } = useForm({
    resolver: zodResolver(profileSchema),
    defaultValues: { full_name: '', phone: '', address: '', image: null, remove_image: false },
  });
  const fileInput = useRef(null);

  useEffect(() => {
    if (profile) reset(toFormValues(profile));
  }, [profile, reset]);

  const picked = watch('image');
  const removeImage = watch('remove_image');
  const previewUrl = useObjectUrl(picked);
  const photo = previewUrl ?? (removeImage ? null : profile?.image) ?? null;

  const pickPhoto = (file) => {
    if (!file) return;
    setValue('image', file, { shouldDirty: true, shouldValidate: true });
    setValue('remove_image', false, { shouldDirty: true });
  };

  const removePhoto = () => {
    if (fileInput.current) fileInput.current.value = '';
    if (picked) {
      setValue('image', null, { shouldDirty: true, shouldValidate: true });
      return;
    }
    setValue('remove_image', true, { shouldDirty: true });
  };

  const onSubmit = handleSubmit(async (values) => {
    clear();
    
    const changed = Object.fromEntries(
      TEXT_FIELDS.filter((field) => dirtyFields[field]).map((field) => [field, values[field]]),
    );
    if (values.image) changed.image = values.image;
    else if (values.remove_image) changed.image = null;
    if (Object.keys(changed).length === 0) return;
    try {
      const saved = await update.mutateAsync(changed);
      if (fileInput.current) fileInput.current.value = '';
      reset(toFormValues(saved));
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

        <div className="profile-page__photo">
          <Avatar className="profile-page__avatar">
            {photo ? <AvatarImage src={photo} alt="Your profile photo" /> : null}
            <AvatarFallback className="profile-page__avatar-fallback">
              {initials(profile?.full_name, profile?.email)}
            </AvatarFallback>
          </Avatar>
          <div className="profile-page__photo-actions">
            <div className="profile-page__photo-buttons">
              <Button type="button" size="sm" variant="outline" onClick={() => fileInput.current?.click()}>
                {photo ? 'Change photo' : 'Choose photo'}
              </Button>
              {photo ? (
                <Button type="button" size="sm" variant="ghost" onClick={removePhoto}>
                  Remove photo
                </Button>
              ) : null}
            </div>
            <input
              ref={fileInput}
              type="file"
              accept={IMAGE_TYPES.join(',')}
              className="profile-page__file-input"
              aria-label="Profile photo"
              onChange={(event) => pickPhoto(event.target.files?.[0])}
            />
            <p className="page-primitive__muted-xs">
              {removeImage && !previewUrl
                ? 'Your photo will be removed when you save.'
                : 'Optional. JPG, PNG or WEBP, up to 2 MB.'}
            </p>
            {errors.image ? <p className="page-primitive__error">{errors.image.message}</p> : null}
          </div>
        </div>

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
