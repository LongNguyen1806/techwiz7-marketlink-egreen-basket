import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { Button } from '../ui/Button';
import { Textarea } from '../ui/Textarea';
import { useFarmerOrder } from '../../hooks/queries/farmer/useFarmerOrders';
import {
  ORDER_ACTIONS,
  allowedOrderActions,
  useFarmerOrderAction,
} from '../../hooks/queries/farmer/useFarmerOrderActions';
import { ApiError } from '../../lib/ApiError';
import { DECLINE_DEFAULTS, declineOrderSchema } from '../../schemas/farmer/order.schema';
import { unitLabel } from '../../utils/labels';
import '../../styles/farmer/FarmerOrderActions.css';

const A = ORDER_ACTIONS;

const BUTTONS = [
  { action: A.ACCEPT, label: 'Accept', variant: 'default' },
  { action: A.DECLINE, label: 'Decline', variant: 'destructive' },
  { action: A.READY, label: 'Ready', variant: 'accent' },
  { action: A.COMPLETE, label: 'Complete', variant: 'default' },
  { action: A.NO_SHOW, label: 'No-show', variant: 'outline' },
];

const CONFIRM_COPY = {
  [A.ACCEPT]: {
    title: 'Accept this pre-order?',
    description: 'The shopper will be told you accepted and can plan their pickup.',
    confirmLabel: 'Accept order',
  },
  [A.READY]: {
    title: 'Mark ready for pickup?',
    description: 'The shopper will be told their order is packed and waiting at your stall.',
    confirmLabel: 'Mark ready',
  },
  [A.COMPLETE]: {
    title: 'Mark this pickup as complete?',
    description: 'Do this once the shopper has collected and paid for the order.',
    confirmLabel: 'Complete pickup',
  },
  [A.NO_SHOW]: {
    title: 'Mark the shopper as a no-show?',
    description: 'Only do this if the shopper did not come during the pickup window.',
    confirmLabel: 'Mark no-show',
    destructive: true,
  },
};

// Codes meaning the order changed under us: close the dialog so the reloaded order shows.
const STALE_CODES = ['RESOURCE_MODIFIED', 'INVALID_STATUS_TRANSITION'];

function DeclineDialog({ order, open, onOpenChange, onSubmit, loading }) {
  // List rows carry no items; load the full order (and its latest version) when needed.
  const detailQuery = useFarmerOrder(order.id, { enabled: open && !order.items });
  const fullOrder = order.items ? order : detailQuery.data;
  const items = fullOrder?.items ?? [];
  const isAccepted = order.status === 'ACCEPTED';

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm({ resolver: zodResolver(declineOrderSchema), defaultValues: DECLINE_DEFAULTS });

  useEffect(() => {
    if (open) reset(DECLINE_DEFAULTS);
  }, [open, reset]);

  const submit = handleSubmit((values) =>
    onSubmit({
      order: fullOrder ?? order,
      reason: values.reason,
      soldOutProductIds: values.sold_out_product_ids,
    }),
  );

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Decline order"
      description="Tell the shopper why (5–500 characters)."
      confirmLabel="Decline"
      destructive
      loading={loading}
      onConfirm={() => void submit()}
    >
      <Textarea
        placeholder="Reason for declining…"
        className="farmer-order-actions__reason"
        maxLength={500}
        aria-invalid={Boolean(errors.reason)}
        {...register('reason')}
      />
      {errors.reason ? <p className="page-primitive__error">{errors.reason.message}</p> : null}

      <div className="page-primitive__stack-2 page-primitive__mt-3">
        <p className="page-primitive__muted-sm">
          {isAccepted
            ? 'Tick any items that are sold out. Unticked items go back into your stock.'
            : 'Tick any items that are sold out so they stop being offered.'}
        </p>
        {!fullOrder && detailQuery.isPending ? <p className="page-primitive__muted-xs">Loading items…</p> : null}
        {detailQuery.isError ? (
          <p className="page-primitive__error">We couldn&apos;t load the items. Close this and try again.</p>
        ) : null}
        <Controller
          control={control}
          name="sold_out_product_ids"
          render={({ field }) => (
            <ul className="page-primitive__list-plain">
              {items.map((item) => {
                const checked = field.value.includes(item.product_id);
                return (
                  <li key={item.product_id}>
                    <label className="page-primitive__inline-row">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() =>
                          field.onChange(
                            checked
                              ? field.value.filter((id) => id !== item.product_id)
                              : [...field.value, item.product_id],
                          )
                        }
                      />
                      <span>
                        {item.product_name} · {item.quantity} {unitLabel(item.unit)}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        />
      </div>
    </ConfirmDialog>
  );
}

DeclineDialog.propTypes = {
  order: PropTypes.object.isRequired,
  open: PropTypes.bool.isRequired,
  onOpenChange: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
  loading: PropTypes.bool,
};

export function FarmerOrderActions({ order, size = 'sm' }) {
  const orderAction = useFarmerOrderAction();
  const [pendingAction, setPendingAction] = useState(null);

  const available = allowedOrderActions(order);
  const buttons = BUTTONS.filter(({ action }) => available.includes(action));
  if (buttons.length === 0) return null;

  const close = () => setPendingAction(null);

  const run = (payload) =>
    orderAction.mutate(
      { order, ...payload, action: pendingAction },
      {
        onSuccess: close,
        onError: (error) => {
          if (STALE_CODES.includes(ApiError.fromUnknown(error).code)) close();
        },
      },
    );

  const busyAction = orderAction.isPending ? orderAction.variables?.action : null;
  const confirmCopy = CONFIRM_COPY[pendingAction];

  return (
    <>
      <div className="farmer-order-actions">
        {buttons.map(({ action, label, variant }) => (
          <Button
            key={action}
            size={size}
            variant={variant}
            data-write
            disabled={orderAction.isPending}
            loading={busyAction === action}
            onClick={() => setPendingAction(action)}
          >
            {label}
          </Button>
        ))}
      </div>

      <DeclineDialog
        order={order}
        open={pendingAction === A.DECLINE}
        onOpenChange={(open) => !open && close()}
        onSubmit={run}
        loading={busyAction === A.DECLINE}
      />

      <ConfirmDialog
        open={Boolean(confirmCopy)}
        onOpenChange={(open) => !open && close()}
        title={confirmCopy?.title ?? ''}
        description={confirmCopy?.description}
        confirmLabel={confirmCopy?.confirmLabel}
        destructive={Boolean(confirmCopy?.destructive)}
        loading={orderAction.isPending}
        onConfirm={() => run({})}
      />
    </>
  );
}

FarmerOrderActions.propTypes = {
  order: PropTypes.shape({
    id: PropTypes.number.isRequired,
    version: PropTypes.number.isRequired,
    status: PropTypes.string.isRequired,
  }).isRequired,
  size: PropTypes.oneOf(['default', 'sm', 'lg', 'icon']),
};
