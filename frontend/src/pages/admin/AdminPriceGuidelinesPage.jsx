import { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Pencil, Plus, Trash2 } from 'lucide-react';

import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { EmptyState } from '@/components/feedback/EmptyState';
import { PageHeader } from '@/components/common/PageHeader';
import { PageSkeleton } from '@/components/feedback/PageSkeleton';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { ApiError } from '@/lib/ApiError';
import { formatMoney } from '@/utils/formatters';
import { UNIT_OPTIONS, unitLabel } from '@/utils/labels';
import { mapServerErrorsToForm } from '@/utils/mapServerErrors';
import { useAdminCategories } from '../../hooks/queries/admin/useAdminCategories';
import {
  useDeletePriceGuideline,
  usePriceGuidelines,
  useSavePriceGuideline,
} from '../../hooks/queries/admin/useAdminAIReview';
import {
  PRICE_GUIDELINE_DEFAULTS,
  guidelineToFormValues,
  priceGuidelineSchema,
} from '../../schemas/admin/priceGuideline.schema';

import './AdminPriceGuidelinesPage.css';

const FIELDS = ['category', 'unit', 'min_price', 'max_price', 'max_stock'];
const toNumberOrNull = (value) => (value === '' || value === null ? null : Number(value));

function FieldError({ error }) {
  return error ? <p className="page-primitive__error">{error.message}</p> : null;
}

FieldError.propTypes = { error: PropTypes.shape({ message: PropTypes.string }) };

/** Add form (no guideline) or inline edit form (existing guideline). */
function GuidelineForm({ guideline, categories, prefill, onDone }) {
  const save = useSavePriceGuideline();
  const isEdit = Boolean(guideline);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isDirty },
  } = useForm({
    resolver: zodResolver(priceGuidelineSchema),
    defaultValues: guideline ? guidelineToFormValues(guideline) : { ...PRICE_GUIDELINE_DEFAULTS, ...prefill },
  });

  const onSubmit = handleSubmit((values) =>
    save.mutate(
      { id: guideline?.id, ...values },
      {
        onSuccess: () => onDone?.(),
        onError: (error) => {
          const apiError = ApiError.fromUnknown(error);
          if (!mapServerErrorsToForm(apiError.fieldErrors, setError, { fields: FIELDS })) {
            setError('root.server', { type: 'server', message: apiError.friendlyMessage });
          }
        },
      },
    ),
  );

  return (
    <form className="admin-price-guidelines__form" onSubmit={onSubmit} noValidate>
      <div className="admin-price-guidelines__form-grid">
        <div className="page-primitive__form-field">
          <label className="page-primitive__label-xs" htmlFor={`pg-category-${guideline?.id ?? 'new'}`}>
            Category
          </label>
          <select
            id={`pg-category-${guideline?.id ?? 'new'}`}
            className="page-primitive__select-full"
            disabled={isEdit}
            {...register('category', { valueAsNumber: true })}
          >
            <option value={0}>Select category</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
          <FieldError error={errors.category} />
        </div>
        <div className="page-primitive__form-field">
          <label className="page-primitive__label-xs" htmlFor={`pg-unit-${guideline?.id ?? 'new'}`}>
            Unit
          </label>
          <select
            id={`pg-unit-${guideline?.id ?? 'new'}`}
            className="page-primitive__select-full"
            disabled={isEdit}
            {...register('unit')}
          >
            {UNIT_OPTIONS.map((unit) => (
              <option key={unit.value} value={unit.value}>
                {unit.label}
              </option>
            ))}
          </select>
          <FieldError error={errors.unit} />
        </div>
        <div className="page-primitive__form-field">
          <Input type="number" step="0.01" min="0.01" label="Lowest usual price ($)" {...register('min_price')} />
          <FieldError error={errors.min_price} />
        </div>
        <div className="page-primitive__form-field">
          <Input type="number" step="0.01" min="0.01" label="Highest usual price ($)" {...register('max_price')} />
          <FieldError error={errors.max_price} />
        </div>
        <div className="page-primitive__form-field">
          <Input
            type="number"
            min="1"
            label="Highest usual stock"
            {...register('max_stock', { setValueAs: toNumberOrNull })}
          />
          <FieldError error={errors.max_stock} />
        </div>
      </div>
      <FieldError error={errors.root?.server} />
      <div className="page-primitive__actions-row">
        {onDone && isEdit ? (
          <Button type="button" variant="outline" size="sm" onClick={onDone}>
            Cancel
          </Button>
        ) : null}
        <Button type="submit" size="sm" loading={save.isPending} disabled={isEdit && !isDirty}>
          {isEdit ? 'Save' : 'Add guideline'}
        </Button>
      </div>
    </form>
  );
}

GuidelineForm.propTypes = {
  guideline: PropTypes.object,
  categories: PropTypes.array.isRequired,
  prefill: PropTypes.object,
  onDone: PropTypes.func,
};

/**
 * What a sensible listing costs per category and unit. The AI listing review flags anything
 * outside these ranges (and anything far from what other stalls charge) for a closer look.
 * Outside a range is never blocked: it is a hint for the admin who decides.
 */
export default function AdminPriceGuidelinesPage() {
  const guidelinesQuery = usePriceGuidelines();
  const categoriesQuery = useAdminCategories();
  const remove = useDeletePriceGuideline();
  const [editingId, setEditingId] = useState(null);
  const [removing, setRemoving] = useState(null);
  const [prefill, setPrefill] = useState(null);
  const [formRound, setFormRound] = useState(0);

  const categories = useMemo(() => categoriesQuery.data ?? [], [categoriesQuery.data]);
  const guidelines = useMemo(() => guidelinesQuery.data ?? [], [guidelinesQuery.data]);
  const byCategory = useMemo(() => {
    const groups = categories.map((category) => ({
      category,
      rows: guidelines.filter((guideline) => guideline.category === category.id),
    }));
    return groups.sort((a, b) => Number(a.rows.length === 0) - Number(b.rows.length === 0));
  }, [categories, guidelines]);

  if (guidelinesQuery.isPending || categoriesQuery.isPending) return <PageSkeleton />;
  if (!guidelinesQuery.data) {
    return <EmptyState title="Guidelines couldn't be loaded" actionLabel="Try again" onAction={() => guidelinesQuery.refetch()} />;
  }

  return (
    <div className="admin-price-guidelines">
      <PageHeader
        title="Price guidelines"
        description="The usual price and stock per category and unit. New listings outside these ranges, or far from what other stalls charge, are flagged by the AI review for a closer look. Nothing is blocked automatically."
      />

      <section className="admin-price-guidelines__create" aria-labelledby="pg-add-title">
        <h2 className="page-primitive__heading" id="pg-add-title">
          <Plus aria-hidden className="admin-price-guidelines__icon" /> Add a guideline
        </h2>
        {/* Keyed on the prefill so "Add" from a category below resets the form to it. */}
        <GuidelineForm
          key={`${formRound}-${prefill ? `${prefill.category}-${prefill.unit}` : 'blank'}`}
          categories={categories}
          prefill={prefill ?? undefined}
          onDone={() => {
            setPrefill(null);
            setFormRound((round) => round + 1);
          }}
        />
      </section>

      <div className="admin-price-guidelines__groups">
        {byCategory.map(({ category, rows }) => (
          <section key={category.id} className="admin-price-guidelines__group" aria-label={category.name}>
            <div className="admin-price-guidelines__group-head">
              <h3 className="admin-price-guidelines__group-title">{category.name}</h3>
              {rows.length === 0 ? (
                <>
                  <Badge variant="outline">No guideline, only the peer-price check runs</Badge>
                  <Button size="sm" variant="ghost" onClick={() => setPrefill({ category: category.id, unit: 'KG' })}>
                    Add for {category.name}
                  </Button>
                </>
              ) : null}
            </div>
            {rows.length ? (
              <div className="page-primitive__table-wrap">
                <table className="page-primitive__table">
                  <thead className="page-primitive__table-head">
                    <tr>
                      <th className="page-primitive__table-th">Unit</th>
                      <th className="page-primitive__table-th">Usual price</th>
                      <th className="page-primitive__table-th">Highest usual stock</th>
                      <th className="page-primitive__table-th">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((guideline) =>
                      editingId === guideline.id ? (
                        <tr key={guideline.id} className="page-primitive__table-row">
                          <td className="page-primitive__table-td" colSpan={4}>
                            <GuidelineForm guideline={guideline} categories={categories} onDone={() => setEditingId(null)} />
                          </td>
                        </tr>
                      ) : (
                        <tr key={guideline.id} className="page-primitive__table-row">
                          <td className="page-primitive__table-td page-primitive__font-medium">{unitLabel(guideline.unit)}</td>
                          <td className="page-primitive__table-td">
                            {formatMoney(guideline.min_price)} – {formatMoney(guideline.max_price)}
                          </td>
                          <td className="page-primitive__table-td">
                            {guideline.max_stock ?? <span className="page-primitive__muted-xs">No limit</span>}
                          </td>
                          <td className="page-primitive__table-td">
                            <div className="page-primitive__actions-row">
                              <Button
                                size="icon"
                                variant="ghost"
                                aria-label={`Edit ${category.name} ${unitLabel(guideline.unit)}`}
                                onClick={() => setEditingId(guideline.id)}
                              >
                                <Pencil aria-hidden size={16} />
                              </Button>
                              <Button
                                size="icon"
                                variant="ghost"
                                aria-label={`Remove ${category.name} ${unitLabel(guideline.unit)}`}
                                onClick={() => setRemoving(guideline)}
                              >
                                <Trash2 aria-hidden size={16} />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>
        ))}
      </div>

      <ConfirmDialog
        open={Boolean(removing)}
        onOpenChange={(open) => !open && setRemoving(null)}
        title="Remove this guideline?"
        description={
          removing
            ? `${removing.category_name} (${unitLabel(removing.unit)}) listings will then only be compared with what other stalls charge.`
            : undefined
        }
        confirmLabel="Remove"
        destructive
        loading={remove.isPending}
        onConfirm={() => remove.mutate(removing.id, { onSettled: () => setRemoving(null) })}
      />
    </div>
  );
}
