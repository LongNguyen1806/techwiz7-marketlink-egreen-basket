import { Link, useParams } from 'react-router-dom';
import { Countdown } from '../../components/common/Countdown';
import { EmptyState } from '../../components/feedback/EmptyState';
import { OrderTimeline } from '../../components/common/OrderTimeline';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { PriceTag } from '../../components/common/PriceTag';
import { StatusBadge } from '../../components/common/StatusBadge';
import { FarmerOrderActions } from '../../components/farmer/FarmerOrderActions';
import { Button } from '../../components/ui/Button';
import { ROUTES } from '../../constants/routes';
import { useFarmerOrder } from '../../hooks/queries/farmer/useFarmerOrders';
import { formatMoney, formatPickupWindow } from '../../utils/formatters';
import { unitLabel } from '../../utils/labels';
import '../../styles/farmer/FarmerOrderDetailPage.css';

const OPEN_STATUSES = ['PLACED', 'ACCEPTED', 'READY_FOR_PICKUP'];

function BackToList() {
  return (
    <Button asChild variant="outline">
      <Link to={ROUTES.FARMER.ORDERS}>← Order list</Link>
    </Button>
  );
}

export default function FarmerOrderDetailPage() {
  const { id } = useParams();
  const query = useFarmerOrder(id);

  if (query.isPending && query.fetchStatus !== 'idle') return <PageSkeleton />;
  if (!query.data) {
    const notFound = !query.isError || query.error?.status === 404;
    return (
      <div className="page-primitive__stack-6">
        {notFound ? (
          <EmptyState title="This order could not be found" description="It may belong to another stall, or the link is wrong." />
        ) : (
          <EmptyState title="This order couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()} />
        )}
        <BackToList />
      </div>
    );
  }

  const order = query.data;
  const isOpen = OPEN_STATUSES.includes(order.status);

  return (
    <div className="page-primitive__stack-6">
      <PageHeader
        title={`#${order.id}`}
        description={`${order.customer.full_name} · ${order.customer.phone}`}
        actions={<StatusBadge status={order.status} />}
      />

      {order.has_pending_change ? (
        <p className="page-primitive__warn-banner">The shopper has asked to change this order.</p>
      ) : null}
      {order.stock_warning ? (
        <p className="page-primitive__warn-banner">Your current stock cannot cover every item in this order.</p>
      ) : null}

      <FarmerOrderActions order={order} size="default" />

      <OrderTimeline status={order.status} history={order.status_history} />

      <div className="page-primitive__grid-2-md">
        <div className="page-primitive__panel">
          <h2 className="page-primitive__heading farmer-order-detail__heading">Pickup</h2>
          <p className="page-primitive__muted-sm">{order.market.name}</p>
          {order.stall_label ? <p className="page-primitive__muted-sm">{order.stall_label}</p> : null}
          <p className="page-primitive__muted-sm farmer-order-detail__countdown--sm">
            {formatPickupWindow(order.pickup_start_at, order.pickup_end_at)}
          </p>
          {isOpen ? (
            <>
              <Countdown className="farmer-order-detail__countdown" targetIso={order.pickup_start_at} label="Until pickup" />
              <Countdown className="farmer-order-detail__countdown--sm" targetIso={order.cutoff_at} label="Cut-off" />
            </>
          ) : null}
        </div>
        <div className="page-primitive__panel">
          <h2 className="page-primitive__heading farmer-order-detail__heading">Note</h2>
          <p className="page-primitive__muted-sm">{order.note || 'No note from the shopper'}</p>
        </div>
      </div>

      <div className="farmer-order-detail__items">
        <ul>
          {order.items.map((item) => (
            <li key={item.id} className="farmer-order-detail__item">
              <div>
                <p className="farmer-order-detail__item-name">{item.product_name}</p>
                <p className="page-primitive__muted-sm">
                  {item.quantity} × <PriceTag amount={item.unit_price} unit={unitLabel(item.unit)} />
                </p>
              </div>
              <p className="farmer-order-detail__item-total">{formatMoney(item.line_total)}</p>
            </li>
          ))}
        </ul>
        <div className="farmer-order-detail__total">
          <span>Total</span>
          <span>{formatMoney(order.total_amount)}</span>
        </div>
      </div>

      <BackToList />
    </div>
  );
}
