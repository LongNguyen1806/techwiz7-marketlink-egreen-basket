import { useQuery } from '@tanstack/react-query';

import { adminApi } from '@/api/admin/adminApi';
import { QUERY_KEYS } from '@/config/constants';
import { Badge } from '@/components/common/badges/Badge';
import { LazyImage } from '@/components/common/cards/LazyImage';
import { RatingStars } from '@/components/common/badges/RatingStars';
import { farmerStatusLabel, farmerStatusVariant } from '@/utils/labels';
import { formatVnd } from '@/utils/formatters';

import './FlagTargetCard.css';

// Each kind of flagged thing already has an admin endpoint that can return exactly one row,
// so this reads the existing ones rather than adding a lookup of its own.
const LOADERS = {
  PRODUCT: async (id) => {
    const page = await adminApi.getModerationProducts({ product_id: id });
    return page.results[0] ?? null;
  },
  PRODUCT_REVIEW: async (id) => {
    const page = await adminApi.getModerationReviews({ review_id: id, type: 'PRODUCT' });
    return page.results[0] ?? null;
  },
  FARMER_REVIEW: async (id) => {
    const page = await adminApi.getModerationReviews({ review_id: id, type: 'FARMER' });
    return page.results[0] ?? null;
  },
  FARMER: (id) => adminApi.getFarmer(id),
  CUSTOMER: (id) => adminApi.getCustomer(id),
};

function Row({ label, children }) {
  if (children === null || children === undefined || children === '') return null;
  return (
    <div className="flag-target__row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function ProductBody({ item }) {
  return (
    <>
      <div className="flag-target__media">
        <LazyImage src={item.image} alt="" className="flag-target__thumb" />
        <div>
          <p className="flag-target__title">{item.name}</p>
          <p className="page-primitive__muted-xs">{item.farmer?.stall_name}</p>
        </div>
      </div>
      <dl className="flag-target__list">
        <Row label="Price">
          {formatVnd(item.price)} / {item.unit}
        </Row>
        <Row label="In stock">{item.stock_quantity}</Row>
        <Row label="Category">{item.category?.name}</Row>
        <Row label="Open orders">{item.open_order_count}</Row>
        <Row label="Description">{item.description}</Row>
        {item.is_hidden_by_admin ? (
          <Row label="Already acted on">
            <Badge variant="danger">
              {item.moderation_action === 'BLOCK' ? 'Taken down' : 'Hidden'}:{' '}
              {item.hidden_reason}
            </Badge>
          </Row>
        ) : null}
      </dl>
    </>
  );
}

function ReviewBody({ item }) {
  return (
    <>
      <div className="flag-target__media">
        <div>
          <RatingStars value={item.rating} />
          <p className="page-primitive__muted-xs">{item.customer_display_name}</p>
        </div>
      </div>
      <dl className="flag-target__list">
        <Row label="About">
          {item.product ? item.product.name : `Stall review · order #${item.order_id}`}
        </Row>
        <Row label="Comment">{item.comment}</Row>
        <Row label="Stall replied">{item.reply}</Row>
        {item.is_hidden_by_admin ? (
          <Row label="Already acted on">
            <Badge variant="danger">Hidden: {item.hidden_reason}</Badge>
          </Row>
        ) : null}
      </dl>
    </>
  );
}

function FarmerBody({ item }) {
  return (
    <>
      <div className="flag-target__media">
        <LazyImage src={item.image} alt="" className="flag-target__thumb" />
        <div>
          <p className="flag-target__title">{item.stall_name}</p>
          <Badge variant={farmerStatusVariant(item.status)}>
            {farmerStatusLabel(item.status)}
          </Badge>
        </div>
      </div>
      <dl className="flag-target__list">
        <Row label="Contact">{item.contact_person}</Row>
        <Row label="Phone">{item.phone}</Row>
        <Row label="Email">{item.email}</Row>
        <Row label="Address">{item.address}</Row>
        <Row label="Why this status">{item.status_reason}</Row>
      </dl>
    </>
  );
}

function CustomerBody({ item }) {
  return (
    <>
      <div className="flag-target__media">
        <div>
          <p className="flag-target__title">{item.full_name}</p>
          <Badge variant={item.is_active ? 'success' : 'danger'}>
            {item.is_active ? 'Active' : 'Locked'}
          </Badge>
        </div>
      </div>
      <dl className="flag-target__list">
        <Row label="Email">{item.email}</Row>
        <Row label="Phone">{item.phone}</Row>
        <Row label="Address">{item.address}</Row>
        <Row label="Why locked">{item.deactivation_reason}</Row>
      </dl>
    </>
  );
}

const BODIES = {
  PRODUCT: ProductBody,
  PRODUCT_REVIEW: ReviewBody,
  FARMER_REVIEW: ReviewBody,
  FARMER: FarmerBody,
  CUSTOMER: CustomerBody,
};

/**
 * The flagged thing itself, read without leaving the queue.
 *
 * Sending the admin off to another screen means coming back to an empty search box and the
 * filters reset, which for a queue worked item by item is the whole cost of the decision.
 */
export function FlagTargetCard({ flag }) {
  const loader = LOADERS[flag?.target_type];
  const query = useQuery({
    queryKey: QUERY_KEYS.ADMIN_FLAG_TARGET(flag?.target_type, flag?.target_id),
    queryFn: () => loader(flag.target_id),
    enabled: Boolean(flag && loader),
  });

  if (!flag) return null;
  if (!loader) {
    return <p className="page-primitive__muted-sm">Nothing to preview for this kind.</p>;
  }
  if (query.isLoading) {
    return <p className="page-primitive__muted-sm">Loading the flagged item…</p>;
  }
  if (query.isError || !query.data) {
    return (
      <p className="page-primitive__muted-sm">
        The flagged item could not be loaded. It may have been deleted since it was flagged.
      </p>
    );
  }

  const Body = BODIES[flag.target_type];
  return (
    <div className="flag-target">
      <Body item={query.data} />
    </div>
  );
}
