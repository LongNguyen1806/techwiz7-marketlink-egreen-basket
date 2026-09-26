import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { MapPin, Phone } from 'lucide-react';
import { Countdown } from '../../components/common/Countdown';
import { DirectionsButton } from '../../components/common/maps/DirectionsButton';
import { FormAlert } from '../../components/common/forms/FormAlert';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Button } from '../../components/ui/Button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../../components/ui/Dialog';
import { Textarea } from '../../components/ui/Textarea';
import { ChangeRequestPanel } from '../../components/customer/orders/ChangeRequestPanel';
import { OrderActions } from '../../components/customer/orders/OrderActions';
import { OrderItemsTable } from '../../components/customer/orders/OrderItemsTable';
import { OrderTimeline } from '../../components/customer/orders/OrderTimeline';
import { useCancelOrder } from '../../hooks/queries/customer/useOrderActions';
import { useCustomerOrder } from '../../hooks/queries/customer/useCustomerOrder';
import { useReorder } from '../../hooks/queries/customer/useReorder';
import { ApiError } from '../../lib/ApiError';
import { formatDate, formatDateTime, formatTime } from '../../utils/formatters';
import './OrderDetailPage.css';

/** C-05 (CU-06, CU-08, CU-09). */
export default function OrderDetailPage() {
  const { orderId } = useParams();
  const { data: order, isLoading } = useCustomerOrder(orderId);
  const cancel = useCancelOrder(orderId);
  const reorder = useReorder();
  const [cancelling, setCancelling] = useState(false);
  const [reason, setReason] = useState('');
  const [error, setError] = useState(null);

  if (isLoading || !order) return <PageSkeleton />;

  const open = ['PLACED', 'ACCEPTED', 'READY_FOR_PICKUP'].includes(order.status);
  const declined = order.status === 'DECLINED';
  const declineReason = declined
    ? order.status_history.find((entry) => entry.to_status === 'DECLINED')?.change_reason
    : null;

  async function confirmCancel() {
    setError(null);
    try {
      // CU-08 takes the version this page was showing: a tab that acted first turns this into 409.
      await cancel.mutateAsync({ version: order.version, reason: reason.trim() || undefined });
      setCancelling(false);
      setReason('');
    } catch (caught) {
      const apiError = ApiError.fromUnknown(caught);
      setCancelling(false);
      setError(apiError.code === 'RESOURCE_MODIFIED'
        ? `${apiError.apiMessage}. Reload the page to see the latest version.`
        : apiError.friendlyMessage);
    }
  }

  return (
    <section className="order-detail">
      <PageHeader
        title={`Order #${order.id}`}
        description={`Placed ${formatDateTime(order.created_at)}`}
        actions={<StatusBadge status={order.status} />}
      />

      <FormAlert message={error} />

      {open ? (
        <Countdown targetIso={order.cutoff_at} label="Edit/cancel until" className="order-detail__cutoff" />
      ) : null}

      {declined && declineReason ? (
        <p className="order-detail__declined" role="status">{declineReason}</p>
      ) : null}

      {order.pending_change ? <ChangeRequestPanel change={order.pending_change} /> : null}

      <div className="order-detail__grid">
        <section className="order-detail__panel" aria-labelledby="pickup-heading">
          <h2 className="order-detail__panel-title" id="pickup-heading">Pickup</h2>

          <p className="order-detail__where">
            <MapPin className="order-detail__icon" aria-hidden />
            <span>
              {order.market.name}
              <span className="order-detail__address">{order.market.address}</span>
              {order.stall_label ? <span className="order-detail__address">{order.stall_label}</span> : null}
            </span>
          </p>

          <p className="order-detail__when">
            {`${formatDate(order.pickup_date)} · ${formatTime(order.pickup_start_at)}–${formatTime(order.pickup_end_at)}`}
          </p>

          <div className="order-detail__contact">
            <span className="order-detail__stall">{order.farmer.stall_name}</span>
            {/* D-026: the stall's phone number is there to be dialled, not just read. */}
            <Button asChild variant="outline" size="sm">
              <a href={`tel:${order.farmer.phone}`}>
                <Phone className="order-detail__icon" aria-hidden />
                {`Call ${order.farmer.phone}`}
              </a>
            </Button>
            <DirectionsButton latitude={order.market.latitude} longitude={order.market.longitude} />
          </div>

          {order.note ? (
            <p className="order-detail__note">
              <span className="order-detail__note-label">Your note</span>
              {order.note}
            </p>
          ) : null}
        </section>

        <section className="order-detail__panel" aria-labelledby="items-heading">
          <h2 className="order-detail__panel-title" id="items-heading">Items</h2>
          <OrderItemsTable items={order.items} totalAmount={order.total_amount} />
        </section>
      </div>

      <OrderActions
        order={order}
        size="default"
        onCancel={() => setCancelling(true)}
        onReorder={() => reorder.mutate(order.id)}
        reorderPending={reorder.isPending}
      />

      <section className="order-detail__panel" aria-labelledby="history-heading">
        <h2 className="order-detail__panel-title" id="history-heading">History</h2>
        <OrderTimeline entries={order.status_history} />
      </section>

      <p className="order-detail__back">
        <Link to="/customer/orders">Back to my orders</Link>
      </p>

      <Dialog open={cancelling} onOpenChange={setCancelling}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{`Cancel order #${order.id}?`}</DialogTitle>
            <DialogDescription>
              This cannot be undone. A change request waiting on this order is dropped with it.
            </DialogDescription>
          </DialogHeader>

          <div className="order-detail__reason">
            <label className="order-detail__reason-label" htmlFor="cancel-reason">
              Reason (optional)
            </label>
            <Textarea
              id="cancel-reason"
              maxLength={500}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </div>

          <div className="order-detail__dialog-actions">
            <Button variant="outline" onClick={() => setCancelling(false)} disabled={cancel.isPending}>
              Keep order
            </Button>
            <Button variant="destructive" loading={cancel.isPending} onClick={confirmCancel}>
              Cancel order
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
