import { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { CalendarX2, Trash2 } from 'lucide-react';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Skeleton } from '../ui/Skeleton';
import { ROUTES } from '../../constants/routes';
import { useCreateClosure, useDeleteClosure, useFarmerClosures } from '../../hooks/queries/farmer/useFarmerClosures';
import { ApiError } from '../../lib/ApiError';
import { CLOSURE_DEFAULTS, makeClosureSchema } from '../../schemas/farmer/market.schema';
import { formatDate, toApiDate } from '../../utils/formatters';
import { mapServerErrorsToForm } from '../../utils/mapServerErrors';
import '../../styles/farmer/FarmerTimeOffPanel.css';

function closureRange(closure) {
  return closure.start_date === closure.end_date
    ? formatDate(closure.start_date)
    : `${formatDate(closure.start_date)} – ${formatDate(closure.end_date)}`;
}

function FieldError({ error }) {
  return error ? <p className="page-primitive__error">{error.message}</p> : null;
}

FieldError.propTypes = { error: PropTypes.shape({ message: PropTypes.string }) };

function AddTimeOffDialog({ open, onClose }) {
  const create = useCreateClosure();
  const today = toApiDate();
  const schema = useMemo(() => makeClosureSchema(today), [today]);
  const [blockingIds, setBlockingIds] = useState([]);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm({ resolver: zodResolver(schema), defaultValues: CLOSURE_DEFAULTS });

  useEffect(() => {
    if (!open) return;
    reset(CLOSURE_DEFAULTS);
    setBlockingIds([]);
  }, [open, reset]);

  const onSubmit = handleSubmit((values) => {
    setBlockingIds([]);
    create.mutate(
      { startDate: values.start_date, endDate: values.end_date, reason: values.reason },
      {
        onSuccess: onClose,
        onError: (error) => {
          const apiError = ApiError.fromUnknown(error);
          if (apiError.is('RESOURCE_IN_USE')) {
            setBlockingIds(apiError.fieldErrors.order_ids ?? []);
            return;
          }
          const mapped = mapServerErrorsToForm(apiError.fieldErrors, setError, {
            fields: ['start_date', 'end_date', 'reason'],
          });
          if (!mapped) setError('root.server', { type: 'server', message: apiError.friendlyMessage });
        },
      },
    );
  });

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={(next) => !next && onClose()}
      title="Add time off"
      description="Shoppers can't book pickups with you on these days, and your stall page shows you're away."
      confirmLabel="Add time off"
      loading={create.isPending}
      onConfirm={() => void onSubmit()}
    >
      <div className="page-primitive__form-grid-2">
        <div className="page-primitive__form-field">
          <Input type="date" label="First day off" min={today} {...register('start_date')} />
          <FieldError error={errors.start_date} />
        </div>
        <div className="page-primitive__form-field">
          <Input type="date" label="Last day off" min={today} {...register('end_date')} />
          <FieldError error={errors.end_date} />
        </div>
      </div>
      <div className="page-primitive__form-field">
        <Input label="Reason shown to shoppers (optional)" maxLength={200} {...register('reason')} />
        <FieldError error={errors.reason} />
      </div>
      <FieldError error={errors.root?.server} />

      {blockingIds.length > 0 ? (
        <div className="page-primitive__warn-banner farmer-time-off__blocking" role="alert">
          <p>You still have open orders on these days. Decline or complete them first:</p>
          <ul className="farmer-time-off__blocking-list">
            {blockingIds.map((orderId) => (
              <li key={orderId}>
                <Link to={ROUTES.FARMER.ORDER(orderId)} className="page-primitive__link-underline">
                  Order #{orderId}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </ConfirmDialog>
  );
}

AddTimeOffDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
};

export function FarmerTimeOffPanel() {
  const closuresQuery = useFarmerClosures();
  const remove = useDeleteClosure();
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState(null);

  const closures = closuresQuery.data ?? [];

  let body;
  if (closuresQuery.isPending) {
    body = <Skeleton className="farmer-time-off__skeleton" />;
  } else if (!closuresQuery.data) {
    body = (
      <p className="page-primitive__muted-sm">
        Your time off couldn&apos;t be loaded.{' '}
        <button type="button" className="page-primitive__link-underline" onClick={() => closuresQuery.refetch()}>
          Try again
        </button>
      </p>
    );
  } else if (closures.length === 0) {
    body = <p className="page-primitive__muted-sm">No time off planned.</p>;
  } else {
    body = (
      <ul className="page-primitive__stack-2">
        {closures.map((closure) => (
          <li key={closure.id} className="page-primitive__list-item-row">
            <span className="farmer-time-off__item">
              <CalendarX2 className="farmer-time-off__icon" aria-hidden />
              <span>
                <span className="page-primitive__font-medium">{closureRange(closure)}</span>
                {closure.reason ? <span className="page-primitive__muted-sm"> · {closure.reason}</span> : null}
              </span>
            </span>
            <Button
              size="icon"
              variant="ghost"
              aria-label={`Remove time off ${closureRange(closure)}`}
              onClick={() => setRemoving(closure)}
            >
              <Trash2 aria-hidden size={16} />
            </Button>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <section className="page-primitive__panel farmer-time-off" aria-labelledby="farmer-time-off-title">
      <div className="farmer-time-off__head">
        <div>
          <h2 className="page-primitive__heading" id="farmer-time-off-title">
            Time off
          </h2>
          <p className="page-primitive__muted-xs">Days you won&apos;t be at any market. Shoppers see this on your stall page.</p>
        </div>
        <Button size="sm" onClick={() => setAdding(true)}>
          + Add time off
        </Button>
      </div>

      {body}

      <AddTimeOffDialog open={adding} onClose={() => setAdding(false)} />

      <ConfirmDialog
        open={Boolean(removing)}
        onOpenChange={(open) => !open && setRemoving(null)}
        title="Remove this time off?"
        description={removing ? `Shoppers will be able to book pickups on ${closureRange(removing)} again.` : undefined}
        confirmLabel="Remove"
        destructive
        loading={remove.isPending}
        onConfirm={() => remove.mutate({ closureId: removing.id }, { onSettled: () => setRemoving(null) })}
      />
    </section>
  );
}
