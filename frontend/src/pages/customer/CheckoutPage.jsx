import { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { CalendarClock, Info } from 'lucide-react';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { DirectionsButton } from '../../components/common/maps/DirectionsButton';
import { FormAlert } from '../../components/common/forms/FormAlert';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Button } from '../../components/ui/Button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../../components/ui/Dialog';
import { Textarea } from '../../components/ui/Textarea';
import { useNow } from '../../hooks/useNow';
import { usePickupOptions } from '../../hooks/queries/customer/usePickupOptions';
import { useCheckout } from '../../hooks/queries/customer/useCheckout';
import { ApiError } from '../../lib/ApiError';
import { cartGroups, isOrderable, useCartStore } from '../../stores/cart.store';
import { formatDate, formatDateTime, formatMoney } from '../../utils/formatters';
import { moneyToNumber } from '../../utils/helpers/domain';
import { cn } from '../../lib/cn';
import './CheckoutPage.css';

/** CU-04 reports a bad item as `groups.<i>.items.<j>.<field>`, which points back at one cart line. */
function readItemErrors(fieldErrors, bodyGroups) {
  const byProduct = {};
  Object.entries(fieldErrors ?? {}).forEach(([key, messages]) => {
    const match = /^groups\.(\d+)\.items\.(\d+)\./.exec(key);
    if (!match) return;
    const item = bodyGroups[Number(match[1])]?.items?.[Number(match[2])];
    if (item) byProduct[item.product_id] = messages[0];
  });
  return byProduct;
}

/** Anything else attached to a group — a window that was taken, a cut-off that passed. */
function readGroupErrors(fieldErrors, bodyGroups) {
  const byFarmer = {};
  Object.entries(fieldErrors ?? {}).forEach(([key, messages]) => {
    const match = /^groups\.(\d+)\.(pickup_slot_id|pickup_date|farmer_id|note)$/.exec(key);
    if (!match) return;
    const group = bodyGroups[Number(match[1])];
    if (group) byFarmer[group.farmer_id] = messages[0];
  });
  return byFarmer;
}

function PickupPicker({ group, selection, onChange, error }) {
  const { data: options, isLoading } = usePickupOptions(group.farmer_id);
  const now = useNow();

  if (isLoading) return <PageSkeleton />;
  if (!options?.length) {
    return (
      <p className="checkout-page__none">
        This stall has no pickup window in the next few days. Remove its items to continue.
      </p>
    );
  }

  // Nothing is preselected in the body: the market and day shown are only the first ones offered,
  // and the body is filled from the window the customer actually picks.
  const market = options.find((option) => option.market_id === selection.market_id) ?? options[0];
  const day = market.dates.find((entry) => entry.date === selection.date) ?? market.dates[0];

  return (
    <div className="checkout-page__picker">
      {options.length > 1 ? (
        <fieldset className="checkout-page__field">
          <legend className="checkout-page__legend">Pickup market</legend>
          <div className="checkout-page__chips">
            {options.map((option) => (
              <label key={option.market_id} className="checkout-page__chip">
                <input
                  type="radio"
                  className="checkout-page__chip-input"
                  name={`market-${group.farmer_id}`}
                  aria-label={option.market_name}
                  checked={option.market_id === market.market_id}
                  onChange={() => onChange({ market_id: option.market_id, date: null, pickup_slot_id: null })}
                />
                <span className="checkout-page__chip-text">{option.market_name}</span>
              </label>
            ))}
          </div>
        </fieldset>
      ) : (
        <p className="checkout-page__where">
          {market.market_name}
          {market.stall_label ? ` · ${market.stall_label}` : ''}
        </p>
      )}

      <fieldset className="checkout-page__field">
        <legend className="checkout-page__legend">Pickup date</legend>
        <div className="checkout-page__chips">
          {market.dates.map((entry) => (
            <label key={entry.date} className="checkout-page__chip">
              <input
                type="radio"
                className="checkout-page__chip-input"
                name={`date-${group.farmer_id}`}
                aria-label={formatDate(entry.date)}
                checked={entry.date === day.date}
                onChange={() => onChange({ market_id: market.market_id, date: entry.date, pickup_slot_id: null })}
              />
              <span className="checkout-page__chip-text">{formatDate(entry.date)}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="checkout-page__field">
        <legend className="checkout-page__legend">Pickup window</legend>
        <div className="checkout-page__chips">
          {day.slots.map((slot) => {
            // PU-08 never returns a window whose cut-off has passed; this catches the one that
            // passes while the page is open (D-007).
            const passed = new Date(slot.cutoff_at).getTime() <= now;
            return (
              <label key={slot.pickup_slot_id} className={cn('checkout-page__chip', passed && 'is-disabled')}>
                <input
                  type="radio"
                  className="checkout-page__chip-input"
                  name={`slot-${group.farmer_id}`}
                  aria-label={`${slot.start_time}–${slot.end_time}`}
                  disabled={passed}
                  checked={slot.pickup_slot_id === selection.pickup_slot_id}
                  onChange={() => onChange({
                    market_id: market.market_id,
                    date: day.date,
                    pickup_slot_id: slot.pickup_slot_id,
                    cutoff_at: slot.cutoff_at,
                  })}
                />
                <span className="checkout-page__chip-text" title={passed ? 'Pre-order cutoff has passed' : undefined}>
                  {`${slot.start_time}–${slot.end_time}`}
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      {selection.cutoff_at ? (
        <p className="checkout-page__cutoff">
          <CalendarClock className="checkout-page__cutoff-icon" aria-hidden />
          {`Edit or cancel until: ${formatDateTime(selection.cutoff_at)}`}
        </p>
      ) : null}

      <div className="checkout-page__where-row">
        <span className="checkout-page__address">{market.market_name}</span>
        <DirectionsButton latitude={market.latitude} longitude={market.longitude} />
      </div>

      <div className="checkout-page__field">
        <label className="checkout-page__legend" htmlFor={`note-${group.farmer_id}`}>
          {`Note for ${group.farmer_stall_name}`}
        </label>
        <Textarea
          id={`note-${group.farmer_id}`}
          maxLength={300}
          value={selection.note ?? ''}
          onChange={(event) => onChange({ note: event.target.value })}
        />
      </div>

      {error ? <p className="checkout-page__error">{error}</p> : null}
    </div>
  );
}

PickupPicker.propTypes = {
  group: PropTypes.object.isRequired,
  selection: PropTypes.object.isRequired,
  onChange: PropTypes.func.isRequired,
  error: PropTypes.string,
};

/** C-02 (CU-04, D-004). One request, N independent orders, all or nothing. */
export default function CheckoutPage() {
  const lines = useCartStore((state) => state.lines);
  const checkout = useCheckout();
  const [selections, setSelections] = useState({});
  const [confirming, setConfirming] = useState(false);
  const [itemErrors, setItemErrors] = useState({});
  const [groupErrors, setGroupErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [limitMessage, setLimitMessage] = useState(null);

  const groups = useMemo(
    () => cartGroups(lines)
      .map((group) => ({ ...group, lines: group.lines.filter(isOrderable) }))
      .filter((group) => group.lines.length > 0),
    [lines],
  );

  const body = {
    groups: groups.map((group) => {
      const selection = selections[group.farmer_id] ?? {};
      const note = selection.note?.trim();
      return {
        farmer_id: group.farmer_id,
        pickup_slot_id: selection.pickup_slot_id,
        pickup_date: selection.date,
        ...(note ? { note } : {}),
        items: group.lines.map((line) => ({ product_id: line.product_id, quantity: line.quantity })),
      };
    }),
  };
  const ready = groups.length > 0 && body.groups.every((group) => group.pickup_slot_id && group.pickup_date);
  const total = groups.reduce((sum, group) => sum + group.subtotal, 0);

  function update(farmerId, patch) {
    setSelections((current) => ({ ...current, [farmerId]: { ...current[farmerId], ...patch } }));
  }

  async function place() {
    setItemErrors({});
    setGroupErrors({});
    setFormError(null);
    try {
      await checkout.mutateAsync(body);
    } catch (error) {
      const apiError = ApiError.fromUnknown(error);
      setConfirming(false);
      if (apiError.code === 'OPEN_ORDER_LIMIT_EXCEEDED') {
        setLimitMessage(apiError.apiMessage);
        return;
      }
      const items = readItemErrors(apiError.fieldErrors, body.groups);
      const perGroup = readGroupErrors(apiError.fieldErrors, body.groups);
      setItemErrors(items);
      setGroupErrors(perGroup);
      if (Object.keys(items).length === 0 && Object.keys(perGroup).length === 0) {
        setFormError(apiError.friendlyMessage);
      }
    }
  }

  if (groups.length === 0) {
    return (
      <section className="checkout-page">
        <PageHeader title="Checkout" />
        <p className="checkout-page__none">
          There is nothing to order. <Link to="/customer/cart">Back to cart</Link>
        </p>
      </section>
    );
  }

  return (
    <section className="checkout-page">
      <PageHeader
        title="Checkout"
        description={`You are placing ${groups.length} separate order(s) — one per stall.`}
      />

      <FormAlert message={formError} />

      <div className="checkout-page__groups">
        {groups.map((group) => (
          <section key={group.farmer_id} className="checkout-page__group" aria-labelledby={`group-${group.farmer_id}`}>
            <h2 className="checkout-page__group-title" id={`group-${group.farmer_id}`}>
              {group.farmer_stall_name}
            </h2>

            <ul className="checkout-page__items">
              {group.lines.map((line) => (
                <li key={line.product_id} className="checkout-page__item" aria-label={line.name}>
                  <span className="checkout-page__item-name">{`${line.name} × ${line.quantity} ${line.unit}`}</span>
                  <span className="checkout-page__item-amount">
                    {formatMoney(moneyToNumber(line.price) * line.quantity)}
                  </span>
                  {itemErrors[line.product_id] ? (
                    <p className="checkout-page__error">{itemErrors[line.product_id]}</p>
                  ) : null}
                </li>
              ))}
            </ul>

            <PickupPicker
              group={group}
              selection={selections[group.farmer_id] ?? {}}
              onChange={(patch) => update(group.farmer_id, patch)}
              error={groupErrors[group.farmer_id]}
            />
          </section>
        ))}
      </div>

      <aside className="checkout-page__summary">
        <p className="checkout-page__total">
          <span>Total</span>
          <span className="checkout-page__total-value">{formatMoney(total)}</span>
        </p>
        <Button size="lg" disabled={!ready} onClick={() => setConfirming(true)}>
          {`Confirm ${groups.length} orders`}
        </Button>
        <p className="checkout-page__hint">
          <Info className="checkout-page__hint-icon" aria-hidden />
          Stock is reserved only when the farmer accepts your order.
        </p>
        <p className="checkout-page__hint">Pay in cash at the stall when you collect.</p>
      </aside>

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={`Place ${groups.length} orders?`}
        description={`Each stall confirms its own order. Total ${formatMoney(total)}, paid on pickup.`}
        confirmLabel={`Place ${groups.length} orders`}
        loading={checkout.isPending}
        onConfirm={place}
      />

      <Dialog open={limitMessage !== null} onOpenChange={() => setLimitMessage(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Too many orders waiting</DialogTitle>
            <DialogDescription>{limitMessage}</DialogDescription>
          </DialogHeader>
          <div className="checkout-page__dialog-actions">
            <Button variant="outline" onClick={() => setLimitMessage(null)}>Close</Button>
            <Button asChild>
              <Link to="/customer/orders">My orders</Link>
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
