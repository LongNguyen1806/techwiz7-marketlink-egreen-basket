import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Info, Trash2 } from 'lucide-react';
import { FormAlert } from '../../components/common/forms/FormAlert';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { QuantityStepper } from '../../components/common/QuantityStepper';
import { Button } from '../../components/ui/Button';
import { Textarea } from '../../components/ui/Textarea';
import { useCustomerOrder } from '../../hooks/queries/customer/useCustomerOrder';
import { useModifyOrder } from '../../hooks/queries/customer/useOrderActions';
import { usePickupOptions } from '../../hooks/queries/customer/usePickupOptions';
import { useNow } from '../../hooks/useNow';
import { ApiError } from '../../lib/ApiError';
import { MAX_QUANTITY } from '../../stores/cart.store';
import { formatDate, formatMoney } from '../../utils/formatters';
import { moneyToNumber } from '../../utils/helpers/domain';
import { cn } from '../../lib/cn';
import '../../styles/customer/EditOrderPage.css';


function readItemErrors(fieldErrors, items) {
  const byProduct = {};
  Object.entries(fieldErrors ?? {}).forEach(([key, messages]) => {
    const match = /^items\.(\d+)\./.exec(key);
    if (!match) return;
    const item = items[Number(match[1])];
    if (item) byProduct[item.product_id] = messages[0];
  });
  return byProduct;
}


export default function EditOrderPage() {
  const { orderId } = useParams();
  const navigate = useNavigate();
  const { data: order, isLoading } = useCustomerOrder(orderId);
  const modify = useModifyOrder(orderId);
  const now = useNow();

  const [lines, setLines] = useState(null);
  const [note, setNote] = useState(null);
  const [slot, setSlot] = useState(null);
  const [itemErrors, setItemErrors] = useState({});
  const [formError, setFormError] = useState(null);

  const { data: options } = usePickupOptions(order?.farmer?.id);

  if (isLoading || !order) return <PageSkeleton />;

  const current = lines ?? order.items.map((item) => ({
    product_id: item.product_id,
    product_name: item.product_name,
    unit: item.unit,
    unit_price: item.unit_price,
    quantity: item.quantity,
  }));
  const noteValue = note ?? order.note ?? '';
  const isChangeRequest = order.status === 'ACCEPTED';
  const empty = current.length === 0;
  const total = current.reduce((sum, line) => sum + moneyToNumber(line.unit_price) * line.quantity, 0);

  function setQuantity(productId, quantity) {
    setLines(current.map((line) => (line.product_id === productId ? { ...line, quantity } : line)));
  }

  function remove(productId) {
    setLines(current.filter((line) => line.product_id !== productId));
  }

  async function save() {
    setItemErrors({});
    setFormError(null);
    const items = current.map((line) => ({ product_id: line.product_id, quantity: line.quantity }));
    const body = {
      items,
      note: noteValue,
      
      ...(slot ? { pickup_slot_id: slot.pickup_slot_id, pickup_date: slot.date } : {}),
    };

    try {
      await modify.mutateAsync({ version: order.version, body });
      navigate(`/customer/orders/${order.id}`);
    } catch (caught) {
      const apiError = ApiError.fromUnknown(caught);
      const perItem = readItemErrors(apiError.fieldErrors, items);
      setItemErrors(perItem);
      if (Object.keys(perItem).length === 0) {
        setFormError(apiError.code === 'RESOURCE_MODIFIED'
          ? `${apiError.apiMessage}. Reload the order and try again.`
          : apiError.friendlyMessage);
      }
    }
  }

  return (
    <section className="edit-order">
      <PageHeader
        title={`Edit order #${order.id}`}
        description={isChangeRequest
          ? 'The order keeps its current contents until the farmer decides.'
          : 'Changes apply immediately, until the cut-off.'}
      />

      <FormAlert message={formError} />

      {isChangeRequest ? (
        <p className="edit-order__warning">
          <Info className="edit-order__warning-icon" aria-hidden />
          Your changes will be sent to the farmer for approval. Nothing changes on the order until then.
        </p>
      ) : null}

      <section className="edit-order__panel" aria-labelledby="edit-items">
        <h2 className="edit-order__panel-title" id="edit-items">Items</h2>

        <ul className="edit-order__lines">
          {current.map((line) => (
            <li className="edit-order__line" key={line.product_id} aria-label={line.product_name}>
              <span className="edit-order__line-name">{line.product_name}</span>
              <span className="edit-order__line-price">{`${formatMoney(line.unit_price)} / ${line.unit}`}</span>
              <QuantityStepper
                value={line.quantity}
                max={MAX_QUANTITY}
                onChange={(quantity) => setQuantity(line.product_id, quantity)}
              />
              <span className="edit-order__line-total">
                {formatMoney(moneyToNumber(line.unit_price) * line.quantity)}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Remove ${line.product_name}`}
                onClick={() => remove(line.product_id)}
              >
                <Trash2 className="edit-order__line-icon" aria-hidden />
              </Button>
              {itemErrors[line.product_id] ? (
                <p className="edit-order__error">{itemErrors[line.product_id]}</p>
              ) : null}
            </li>
          ))}
        </ul>

        {empty ? (
          <p className="edit-order__error">
            An order must contain at least one item. To call it off, cancel the order instead.
          </p>
        ) : (
          <p className="edit-order__total">
            <span>New total</span>
            <span className="edit-order__total-value">{formatMoney(total)}</span>
          </p>
        )}
      </section>

      <section className="edit-order__panel" aria-labelledby="edit-pickup">
        <h2 className="edit-order__panel-title" id="edit-pickup">Pickup window</h2>
        <p className="edit-order__current">
          {`Currently ${formatDate(order.pickup_date)}. Choose another window only if you want to move it.`}
        </p>

        {(options ?? []).map((option) => (
          <div className="edit-order__market" key={option.market_id}>
            <p className="edit-order__market-name">{option.market_name}</p>
            <div className="edit-order__slots">
              {option.dates.flatMap((entry) => entry.slots.map((pickup) => {
                const passed = new Date(pickup.cutoff_at).getTime() <= now;
                const label = `${pickup.start_time}–${pickup.end_time}`;
                return (
                  <label
                    className={cn('edit-order__slot', passed && 'is-disabled')}
                    key={`${entry.date}-${pickup.pickup_slot_id}`}
                  >
                    <input
                      type="radio"
                      className="edit-order__slot-input"
                      name="new-slot"
                      aria-label={`${formatDate(entry.date)} ${label}`}
                      disabled={passed}
                      checked={slot?.pickup_slot_id === pickup.pickup_slot_id && slot?.date === entry.date}
                      onChange={() => setSlot({ pickup_slot_id: pickup.pickup_slot_id, date: entry.date })}
                    />
                    <span className="edit-order__slot-text">{`${formatDate(entry.date)} · ${label}`}</span>
                  </label>
                );
              }))}
            </div>
          </div>
        ))}
      </section>

      <section className="edit-order__panel" aria-labelledby="edit-note">
        <h2 className="edit-order__panel-title" id="edit-note">Note for the stall</h2>
        <Textarea
          id="edit-note-field"
          aria-labelledby="edit-note"
          maxLength={300}
          value={noteValue}
          onChange={(event) => setNote(event.target.value)}
        />
      </section>

      <div className="edit-order__actions">
        <Button asChild variant="outline">
          <Link to={`/customer/orders/${order.id}`}>Back to the order</Link>
        </Button>
        <Button disabled={empty} loading={modify.isPending} onClick={save}>
          {isChangeRequest ? 'Send change request' : 'Save changes'}
        </Button>
      </div>
    </section>
  );
}
