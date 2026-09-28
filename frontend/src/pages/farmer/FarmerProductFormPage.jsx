import { useMemo, useState } from 'react';
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
import { ListingPrecheck } from '../../components/farmer/ListingPrecheck';
import { MarketChecklist, isSellingMarket } from '../../components/farmer/MarketChecklist';
import { useFarmerMarkets } from '../../hooks/queries/farmer/useFarmerMarkets';
import { useFarmerProduct, useSaveFarmerProduct } from '../../hooks/queries/farmer/useFarmerProducts';
import { useCategories, usePublicConfig } from '../../hooks/queries/guest/usePublicCatalog';
import { ApiError } from '../../lib/ApiError';
import {
  DEFAULT_MAX_UPLOAD_MB,
  IMAGE_TYPES,
  MAX_PER_ORDER,
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



function buildPayload(values, { isEdit, dirtyFields }) {
  const keys = isEdit ? Object.keys(dirtyFields) : FORM_FIELDS;
  const payload = {};
  keys.forEach((key) => {
    if (key === 'remove_image') return;
    if (key === 'image' && !values.image) return;
    payload[key] = values[key];
  });
  if (isEdit && values.remove_image && !values.image) payload.image = null;
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
  const marketsQuery = useFarmerMarkets();
  const farmerMarkets = useMemo(() => marketsQuery.data ?? [], [marketsQuery.data]);
  const productQuery = useFarmerProduct(productId, { enabled: isEdit });
  const product = productQuery.data;
  const save = useSaveFarmerProduct(productId);

  const serverValues = useMemo(() => (product ? productToFormValues(product) : undefined), [product]);
  const createValues = useMemo(
    () =>
      !isEdit && marketsQuery.data
        ? {
            ...PRODUCT_DEFAULTS,
            market_ids: marketsQuery.data.filter(isSellingMarket).map((item) => item.market.id),
          }
        : undefined,
    [isEdit, marketsQuery.data],
  );
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: PRODUCT_DEFAULTS,
    values: isEdit ? serverValues : createValues,
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
  const removeImage = watch('remove_image');
  const shownImage = previewUrl ?? (removeImage ? null : product?.image) ?? null;
  const [fileInputKey, setFileInputKey] = useState(0);

  
  const categoryOptions = useMemo(() => {
    const list = categoriesQuery.data ?? [];
    const current = product?.category;
    return current && !list.some((category) => category.id === current.id) ? [...list, current] : list;
  }, [categoriesQuery.data, product]);

  const pickImage = (file) => {
    if (!file) return;
    setValue('image', file, { shouldDirty: true, shouldValidate: true });
    setValue('remove_image', false, { shouldDirty: true });
  };

  const removePhoto = () => {
    setFileInputKey((key) => key + 1);
    if (watch('image')) {
      setValue('image', null, { shouldDirty: true, shouldValidate: true });
      return;
    }
    setValue('remove_image', true, { shouldDirty: true });
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

  
  const locked = Boolean(product?.is_archived || product?.is_hidden_by_admin);

  return (
    <div className="farmer-product-form-page">
      <PageHeader
        title={isEdit ? 'Edit produce' : 'Add produce'}
        description={
          isEdit
            ? 'Update the photo, price, stock and the markets this item is sold at.'
            : 'Add a photo, choose where it is sold, and set price and stock. New produce is checked automatically; most listings go on sale within minutes.'
        }
      />

      {!locked && product?.review_status === 'PENDING' ? (
        <p className="page-primitive__warn-banner">Waiting for review. Shoppers cannot see this listing until it passes.</p>
      ) : null}
      {!locked && product?.review_status === 'REJECTED' ? (
        <p className="page-primitive__warn-banner">
          Not approved{product.review_note ? `: ${product.review_note}` : ''}. Fix it and save to send it for review
          again.
        </p>
      ) : null}
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
              <>
                <LazyImage src={shownImage} alt="Product photo preview" className="farmer-product-form-page__preview" />
                {!locked ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="farmer-product-form-page__remove-photo"
                    onClick={removePhoto}
                  >
                    Remove photo
                  </Button>
                ) : null}
              </>
            ) : null}
            {removeImage && !previewUrl ? (
              <p className="page-primitive__muted-xs">The current photo will be removed when you save.</p>
            ) : null}
            <p className="farmer-product-form-page__dropzone-title">Drag and drop an image or choose a file</p>
            <p className="page-primitive__muted-xs">JPG, PNG or WEBP, up to {maxUploadMb} MB</p>
            <Input
              key={fileInputKey}
              type="file"
              accept={IMAGE_TYPES.join(',')}
              aria-label="Product photo"
              className="farmer-product-form-page__file-input"
              disabled={locked}
              onChange={(event) => pickImage(event.target.files?.[0])}
            />
            <FieldError error={errors.image} />
          </div>
          {!locked ? <ListingPrecheck values={watch()} productId={productId} /> : null}
        </div>

        <div className="farmer-product-form-page__fields">
          <section className="farmer-product-form-page__section" aria-labelledby="product-section-basics">
            <header className="farmer-product-form-page__section-head">
              <h2 id="product-section-basics" className="farmer-product-form-page__section-title">
                1. The produce
              </h2>
              {!locked && product?.review_status === 'APPROVED' ? (
                <p className="page-primitive__muted-xs">
                  Changing the name, description, photo or category sends it back for review.
                </p>
              ) : null}
            </header>
            <div className="page-primitive__form-field">
              <Input id="name" label="Product name" {...register('name')} />
              <FieldError error={errors.name} />
            </div>
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
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" rows={4} maxLength={1000} {...register('description')} />
              <FieldError error={errors.description} />
            </div>
          </section>

          <section className="farmer-product-form-page__section" aria-labelledby="product-section-stock">
            <header className="farmer-product-form-page__section-head">
              <h2 id="product-section-stock" className="farmer-product-form-page__section-title">
                2. Price and stock
              </h2>
              <p className="page-primitive__muted-xs">Price, stock and limits can change any time without a new review.</p>
            </header>
            <div className="farmer-product-form-page__grid-3">
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
              <div className="page-primitive__form-field farmer-product-form-page__field-bottom">
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
              <div className="page-primitive__form-field farmer-product-form-page__field-bottom">
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
            </div>
            <div className="farmer-product-form-page__grid-3">
              <div className="page-primitive__form-field">
                <Input
                  id="weekly_default_quantity"
                  type="number"
                  inputMode="numeric"
                  min="0"
                  label="Weekly default stock"
                  {...register('weekly_default_quantity', { setValueAs: toNumberOrNull })}
                />
                <FieldError error={errors.weekly_default_quantity} />
              </div>
              <div className="page-primitive__form-field">
                <Input
                  id="min_per_order"
                  type="number"
                  inputMode="numeric"
                  min="1"
                  max={MAX_PER_ORDER}
                  label="Min per order"
                  {...register('min_per_order', { setValueAs: toNumberOrNaN })}
                />
                <FieldError error={errors.min_per_order} />
              </div>
              <div className="page-primitive__form-field">
                <Input
                  id="max_per_order"
                  type="number"
                  inputMode="numeric"
                  min="1"
                  max={MAX_PER_ORDER}
                  label="Max per order"
                  {...register('max_per_order', { setValueAs: toNumberOrNull })}
                />
                <FieldError error={errors.max_per_order} />
              </div>
            </div>
            <p className="page-primitive__muted-xs">
              Weekly default: leave blank to skip this item in the weekly reset. Min 1 means any amount; leave max blank
              for no limit.
            </p>
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
          </section>

          <section className="farmer-product-form-page__section" aria-labelledby="product-section-markets">
            <header className="farmer-product-form-page__section-head">
              <h2 id="product-section-markets" className="farmer-product-form-page__section-title">
                3. Where it is sold
              </h2>
              <p className="page-primitive__muted-xs">
                Shoppers can only collect this item at the markets you tick. Stock is shared across them.
              </p>
            </header>
            {marketsQuery.isPending ? (
              <p className="page-primitive__muted-xs">Loading your markets…</p>
            ) : farmerMarkets.length === 0 ? (
              <p className="page-primitive__warn-banner">
                You have no markets yet. Ask to join one in <Link to={ROUTES.FARMER.MARKETS}>Markets &amp; slots</Link>.
              </p>
            ) : (
              <Controller
                control={control}
                name="market_ids"
                render={({ field }) => (
                  <MarketChecklist
                    markets={farmerMarkets}
                    value={field.value}
                    onChange={(next) => field.onChange(next)}
                    disabled={locked}
                  />
                )}
              />
            )}
            <FieldError error={errors.market_ids} />
          </section>

          <FieldError error={errors.root?.server} />
        </div>

        <div className="farmer-product-form-page__actions">
          <Button asChild variant="outline">
            <Link to={ROUTES.FARMER.PRODUCTS}>Cancel</Link>
          </Button>
          <Button type="submit" data-write loading={save.isPending} disabled={locked || (isEdit && !isDirty)}>
            {isEdit ? 'Save changes' : 'Save'}
          </Button>
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
