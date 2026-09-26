import { useMemo } from 'react';
import PropTypes from 'prop-types';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link } from 'react-router-dom';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { EmptyState } from '../../components/feedback/EmptyState';
import { LazyImage } from '../../components/common/LazyImage';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { OperatingDaysPicker } from '../../components/farmer/OperatingDaysPicker';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/Avatar';
import { Button } from '../../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { Label } from '../../components/ui/Label';
import { Textarea } from '../../components/ui/Textarea';
import { ROUTES } from '../../constants/routes';
import { useObjectUrl } from '../../hooks/common/useObjectUrl';
import { useUnsavedChangesGuard } from '../../hooks/common/useUnsavedChangesGuard';
import { useFarmerProfile, useUpdateFarmerProfile } from '../../hooks/queries/farmer/useFarmerProfile';
import { usePublicConfig } from '../../hooks/queries/guest/usePublicCatalog';
import { ApiError } from '../../lib/ApiError';
import { DEFAULT_MAX_UPLOAD_MB, IMAGE_TYPES } from '../../schemas/farmer/product.schema';
import { PROFILE_FIELDS, makeFarmerProfileSchema, profileToFormValues } from '../../schemas/farmer/profile.schema';
import { mapServerErrorsToForm } from '../../utils/mapServerErrors';
import '../../styles/farmer/FarmerProfilePage.css';

function initials(name, email) {
  const parts = (name ?? '').trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return (email ?? '?').trim().charAt(0).toUpperCase() || '?';
}

function FieldError({ error }) {
  return error ? <p className="page-primitive__error">{error.message}</p> : null;
}

FieldError.propTypes = { error: PropTypes.shape({ message: PropTypes.string }) };

// Only changed fields are sent; a new photo only when one was picked.
function changedFields(values, dirtyFields) {
  const payload = {};
  Object.keys(dirtyFields).forEach((key) => {
    if (key === 'image' && !values.image) return;
    payload[key] = values[key];
  });
  return payload;
}

export default function FarmerProfilePage() {
  const query = useFarmerProfile();
  const update = useUpdateFarmerProfile();
  const configQuery = usePublicConfig();
  const maxUploadMb = configQuery.data?.max_upload_mb ?? DEFAULT_MAX_UPLOAD_MB;
  const schema = useMemo(() => makeFarmerProfileSchema({ maxUploadMb }), [maxUploadMb]);

  const profile = query.data;
  const serverValues = useMemo(() => (profile ? profileToFormValues(profile) : undefined), [profile]);
  const {
    register,
    control,
    handleSubmit,
    reset,
    setValue,
    setError,
    watch,
    formState: { errors, isDirty, dirtyFields },
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: profileToFormValues({}),
    values: serverValues,
    resetOptions: { keepDirtyValues: true },
  });

  const { blocker } = useUnsavedChangesGuard(isDirty && !update.isPending);
  const previewUrl = useObjectUrl(watch('image'));
  const photo = previewUrl ?? profile?.image ?? null;

  const onSubmit = handleSubmit((values) =>
    update.mutate(changedFields(values, dirtyFields), {
      // The saved profile becomes the new clean state of the form.
      onSuccess: (saved) => reset(profileToFormValues(saved)),
      onError: (error) => {
        const apiError = ApiError.fromUnknown(error);
        const orderIds = apiError.fieldErrors.order_ids;
        if (apiError.is('RESOURCE_IN_USE') && Array.isArray(orderIds)) {
          // Removing a weekday that open orders still use (D-031).
          setError('operating_days', {
            type: 'server',
            message: `Open orders ${orderIds.map((id) => `#${id}`).join(', ')} are picked up on the days you removed. Handle them first.`,
          });
          return;
        }
        mapServerErrorsToForm(apiError.fieldErrors, setError, { fields: PROFILE_FIELDS });
      },
    }),
  );

  if (query.isPending) return <PageSkeleton />;
  if (!profile) {
    return <EmptyState title="Profile couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()} />;
  }

  return (
    <div className="farmer-profile-page">
      <PageHeader
        title="Stall profile"
        description="This is what shoppers see when they discover and pre-order from you."
        actions={
          <Button asChild variant="outline" size="sm">
            <Link to={ROUTES.FARMER.CHANGE_PASSWORD}>Change password</Link>
          </Button>
        }
      />

      {photo ? <LazyImage src={photo} alt="" className="farmer-profile-page__banner" /> : null}

      <Card className="farmer-profile-page__card">
        <CardHeader className="farmer-profile-page__header">
          <Avatar className="farmer-profile-page__avatar">
            {photo ? <AvatarImage src={photo} alt="" /> : null}
            <AvatarFallback>{initials(profile.contact_person || profile.stall_name, profile.email)}</AvatarFallback>
          </Avatar>
          <div className="farmer-profile-page__identity">
            <CardTitle className="farmer-profile-page__title-truncate">{profile.stall_name}</CardTitle>
            <p className="farmer-profile-page__email">{profile.email}</p>
          </div>
        </CardHeader>
        <CardContent>
          {/* Every farmer status may edit the profile (backend v1.8), so Save is not write-locked. */}
          <form className="farmer-profile-page__form" onSubmit={onSubmit} noValidate>
            <div className="page-primitive__form-field">
              <Input id="stall_name" label="Stall name" autoComplete="organization" {...register('stall_name')} />
              <FieldError error={errors.stall_name} />
            </div>
            <div className="page-primitive__form-field">
              <Input id="contact_person" label="Contact person" autoComplete="name" {...register('contact_person')} />
              <FieldError error={errors.contact_person} />
            </div>
            <div className="page-primitive__form-field">
              <Input id="phone" type="tel" label="Phone number" autoComplete="tel" {...register('phone')} />
              <FieldError error={errors.phone} />
            </div>
            <div className="page-primitive__form-field">
              <Input id="address" label="Address" autoComplete="street-address" {...register('address')} />
              {!profile.location_found && !dirtyFields.address ? (
                <p className="page-primitive__muted-xs">
                  We couldn&apos;t find this address on the map. Try adding the ward and district.
                </p>
              ) : null}
              <FieldError error={errors.address} />
            </div>
            <div className="page-primitive__form-field">
              <Input
                id="order_cutoff_hours"
                type="number"
                inputMode="numeric"
                min="1"
                max="72"
                label="Order cut-off (hours before pickup)"
                {...register('order_cutoff_hours', {
                  setValueAs: (value) => (value === '' ? Number.NaN : Number(value)),
                })}
              />
              <p className="page-primitive__muted-xs">Changes apply to new orders only.</p>
              <FieldError error={errors.order_cutoff_hours} />
            </div>
            <div className="page-primitive__form-field">
              <Label htmlFor="stall_photo">Stall photo</Label>
              <Input
                id="stall_photo"
                type="file"
                accept={IMAGE_TYPES.join(',')}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) setValue('image', file, { shouldDirty: true, shouldValidate: true });
                }}
              />
              <p className="page-primitive__muted-xs">JPG, PNG or WEBP, up to {maxUploadMb} MB</p>
              <FieldError error={errors.image} />
            </div>
            <div className="page-primitive__form-field farmer-profile-page__field--full">
              <Label>Operating days</Label>
              <Controller
                control={control}
                name="operating_days"
                render={({ field }) => (
                  <OperatingDaysPicker value={field.value} onChange={field.onChange} onBlur={field.onBlur} />
                )}
              />
              <p className="page-primitive__muted-xs">
                Removing a day turns off your pickup slots on that day.
              </p>
              <FieldError error={errors.operating_days} />
            </div>
            <div className="page-primitive__form-field farmer-profile-page__field--full">
              <Label htmlFor="description">About</Label>
              <Textarea id="description" rows={4} maxLength={1000} {...register('description')} />
              <FieldError error={errors.description} />
            </div>
            <div className="farmer-profile-page__field--full">
              <FieldError error={errors.root?.server} />
            </div>
            <div className="farmer-profile-page__actions">
              <Button type="submit" loading={update.isPending} disabled={!isDirty}>
                Save profile
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <ConfirmDialog
        open={blocker.state === 'blocked'}
        onOpenChange={(open) => !open && blocker.reset?.()}
        title="Leave without saving?"
        description="Your changes to the stall profile will be lost."
        confirmLabel="Leave page"
        cancelLabel="Keep editing"
        destructive
        onConfirm={() => blocker.proceed?.()}
      />
    </div>
  );
}
