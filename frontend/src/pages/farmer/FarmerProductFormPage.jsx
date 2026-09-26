import { useMemo } from 'react';
import PropTypes from 'prop-types';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { EmptyState } from '../../components/feedback/EmptyState';
import { LazyImage } from '../../components/common/LazyImage';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Label } from '../../components/ui/Label';
import { Switch } from '../../components/ui/Switch';
import { Textarea } from '../../components/ui/Textarea';
import { ROUTES } from '../../constants/routes';
import { useObjectUrl } from '../../hooks/common/useObjectUrl';
import { useUnsavedChangesGuard } from '../../hooks/common/useUnsavedChangesGuard';
import { useFarmerProduct, useSaveFarmerProduct } from '../../hooks/queries/farmer/useFarmerProducts';
import { useCategories, usePublicConfig } from '../../hooks/queries/guest/usePublicCatalog';
import { ApiError } from '../../lib/ApiError';
import {
  DEFAULT_MAX_UPLOAD_MB,
  IMAGE_TYPES,
  PRODUCT_DEFAULTS,
  makeProductSchema,
  productToFormValues,
} from '../../schemas/farmer/product.schema';
import { UNIT_OPTIONS } from '../../utils/labels';
import { mapServerErrorsToForm } from '../../utils/mapServerErrors';
import '../../styles/farmer/FarmerProductFormPage.css';

const FORM_FIELDS = Object.keys(PRODUCT_DEFAULTS);

const toNumberOrNaN = (value) => (value === '' || value === null ? Number.NaN : Number(value));
const toNumberOrNull = (value) => (value === '' || value === null ? null : Number(value));

// Create sends every field; edit sends only what changed so a stale form never overwrites
// stock that orders moved while the farmer was typing. A new photo is sent only if picked.
function buildPayload(values, { isEdit, dirtyFields }) {
  const keys = isEdit ? Object.keys(dirtyFields) : FORM_FIELDS;
  const payload = {};
  keys.forEach((key) => {
    if (key === 'image' && !values.image) return;
    payload[key] = values[key];
  });
  return payload;
}

function FieldError({ error }) {
  return error ? <p className="page-primitive__error">{error.message}</p> : null;
}

FieldError.propTypes = {
  error: PropTypes.shape({ message: PropTypes.string }),
};

export default function FarmerProductFormPage() {
  const { id } = useParams();
  const isEdit = id !== undefined;
  const productId = isEdit ? Number(id) : undefined;
  const navigate = useNavigate();

  const configQuery = usePublicConfig();
  const maxUploadMb = configQuery.data?.max_upload_mb ?? DEFAULT_MAX_UPLOAD_MB;
  const schema = useMemo(() => makeProductSchema({ maxUploadMb }), [maxUploadMb]);

  const categoriesQuery = useCategories();
  const productQuery = useFarmerProduct(productId, { enabled: isEdit });
  const product = productQuery.data;
  const save = useSaveFarmerProduct(productId);

  // Server values fill the form once loaded; fields the farmer already changed are kept.
  const serverValues = useMemo(() => (product ? productToFormValues(product) : undefined), [product]);
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: PRODUCT_DEFAULTS,
    values: serverValues,
    resetOptions: { keepDirtyValues: true },
  });
  const {
    register,
    control,
    handleSubmit,
    setValue,
    setError,
    watch,
    formState: { errors, isDirty, dirtyFields },
  } = form;

  const { blocker, allowNavigation } = useUnsavedChangesGuard(isDirty && !save.isSuccess);
  const previewUrl = useObjectUrl(watch('image'));
  const shownImage = previewUrl ?? product?.image ?? null;

  // An inactive category is missing from the public list; keep the product's own option.
  const categoryOptions = useMemo(() => {
    const list = categoriesQuery.data ?? [];
    const current = product?.category;
    return current && !list.some((category) => category.id === current.id) ? [...list, current] : list;
  }, [categoriesQuery.data, product]);

  const pickImage = (file) => {
    if (file) setValue('image', file, { shouldDirty: true, shouldValidate: true });
  };

  const onSubmit = handleSubmit((values) =>
    save.mutate(buildPayload(values, { isEdit, dirtyFields }), {
      onSuccess: () => {
        allowNavigation();
        navigate(ROUTES.FARMER.PRODUCTS);
      },
      onError: (error) =>
        mapServerErrorsToForm(ApiError.fromUnknown(error).fieldErrors, setError, { fields: FORM_FIELDS }),
    }),
  );

  if (isEdit && productQuery.isPending && productQuery.fetchStatus !== 'idle') return <PageSkeleton />;
  if (isEdit && !product) {
    const notFound = !productQuery.isError || productQuery.error?.status === 404;
    return notFound ? (
      <EmptyState title="This product could not be found" description="It may have been removed, or the link is wrong." />
    ) : (
      <EmptyState title="Product couldn't be loaded" actionLabel="Try again" onAction={() => productQuery.refetch()} />
    );
  }

  // The backend refuses changes to archived or admin-hidden products.
  const locked = Boolean(product?.is_archived || product?.is_hidden_by_admin);

  return (
    <div className="farmer-product-form-page">
      <PageHeader
        title={isEdit ? 'Edit produce' : 'Add produce'}
        description="Add a photo, set price and stock, then open it for pre-order."
      />

      {locked ? (
        <p className="page-primitive__warn-banner">
          {product.is_archived
            ? 'This product is archived, so it can no longer be edited.'
            : 'An administrator has hidden this product, so it cannot be edited.'}
        </p>
      ) : null}

      <form className="farmer-product-form-page__form" onSubmit={onSubmit} noValidate>
        <div className="farmer-product-form-page__media">
          <div
            className="farmer-product-form-page__dropzone"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              pickImage(event.dataTransfer.files[0]);
            }}
          >
            {shownImage ? (
              <LazyImage src={shownImage} alt="Product photo preview" className="farmer-product-form-page__preview" />
            ) : null}
            <p className="farmer-product-form-page__dropzone-title">Drag and drop an image or choose a file</p>
            <p className="page-primitive__muted-xs">JPG, PNG or WEBP, up to {maxUploadMb} MB</p>
            <Input
              type="file"
              accept={IMAGE_TYPES.join(',')}
              aria-label="Product photo"
              className="farmer-product-form-page__file-input"
              disabled={locked}
              onChange={(event) => pickImage(event.target.files?.[0])}
            />
            <FieldError error={errors.image} />
          </div>
        </div>

        <div className="farmer-product-form-page__fields">
          <div className="page-primitive__form-field">
            <Input id="name" label="Product name" {...register('name')} />
            <FieldError error={errors.name} />
          </div>

          <div className="page-primitive__form-grid-2">
            <div className="page-primitive__form-field">
              <Label htmlFor="category_id">Category</Label>
              <select
                id="category_id"
                className="page-primitive__select-full"
                {...register('category_id', { valueAsNumber: true })}
              >
                <option value={0}>{categoriesQuery.isPending ? 'Loading categories…' : 'Select category'}</option>
                {categoryOptions.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
              <FieldError error={errors.category_id} />
            </div>
            <div className="page-primitive__form-field">
              <Label htmlFor="unit">Unit</Label>
              <select id="unit" className="page-primitive__select-full" {...register('unit')}>
                {UNIT_OPTIONS.map((unit) => (
                  <option key={unit.value} value={unit.value}>
                    {unit.label}
                  </option>
                ))}
              </select>
              <FieldError error={errors.unit} />
            </div>
          </div>

          <div className="farmer-product-form-page__grid-3">
            <div className="page-primitive__form-field">
              <Input
                id="price"
                type="number"
                inputMode="decimal"
                step="0.01"
                min="0.01"
                label="Price ($)"
                {...register('price')}
              />
              <FieldError error={errors.price} />
            </div>
            <div className="page-primitive__form-field">
              <Input
                id="stock_quantity"
                type="number"
                inputMode="numeric"
                min="0"
                label="Stock"
                {...register('stock_quantity', { setValueAs: toNumberOrNaN })}
              />
              <FieldError error={errors.stock_quantity} />
            </div>
            <div className="page-primitive__form-field">
              <Input
                id="weekly_default_quantity"
                type="number"
                inputMode="numeric"
                min="0"
                label="Weekly default stock"
                {...register('weekly_default_quantity', { setValueAs: toNumberOrNull })}
              />
              <p className="page-primitive__muted-xs">Leave blank to skip this item in the weekly reset.</p>
              <FieldError error={errors.weekly_default_quantity} />
            </div>
          </div>

          <div className="page-primitive__form-field">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={4} maxLength={1000} {...register('description')} />
            <FieldError error={errors.description} />
          </div>

          <div className="farmer-product-form-page__toggle-row">
            <div>
              <p className="page-primitive__font-medium">Open for sale</p>
              <p className="page-primitive__muted-xs">Turn off to pause accepting orders</p>
            </div>
            <Controller
              control={control}
              name="is_available"
              render={({ field }) => (
                <Switch checked={field.value} onCheckedChange={field.onChange} aria-label="Open for sale" />
              )}
            />
          </div>

          <FieldError error={errors.root?.server} />

          <div className="farmer-product-form-page__actions">
            <Button asChild variant="outline">
              <Link to={ROUTES.FARMER.PRODUCTS}>Cancel</Link>
            </Button>
            <Button
              type="submit"
              data-write
              loading={save.isPending}
              disabled={locked || (isEdit && !isDirty)}
            >
              {isEdit ? 'Save changes' : 'Save'}
            </Button>
          </div>
        </div>
      </form>

      <ConfirmDialog
        open={blocker.state === 'blocked'}
        onOpenChange={(open) => !open && blocker.reset?.()}
        title="Leave without saving?"
        description="Your changes to this product will be lost."
        confirmLabel="Leave page"
        cancelLabel="Keep editing"
        destructive
        onConfirm={() => blocker.proceed?.()}
      />
    </div>
  );
}
