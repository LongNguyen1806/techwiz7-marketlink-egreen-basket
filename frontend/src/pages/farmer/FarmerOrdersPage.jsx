import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { Printer } from 'lucide-react';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { StatusBadge } from '../../components/common/StatusBadge';
import { FarmerOrderActions } from '../../components/farmer/FarmerOrderActions';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/Tabs';
import { ROUTES } from '../../constants/routes';
import { useDebouncedSearchParam } from '../../hooks/common/useDebouncedSearchParam';
import { useUrlFilters } from '../../hooks/common/useUrlFilters';
import {
  useFarmerOrderList,
  useFarmerOrderTabCounts,
  useFarmerOverdueOrders,
  usePickingList,
} from '../../hooks/queries/farmer/useFarmerOrders';
import { formatMoney, formatPickupWindow, toApiDate } from '../../utils/formatters';
import { unitLabel } from '../../utils/labels';
import '../../styles/farmer/FarmerOrdersPage.css';


const TABS = [
  { id: 'pending', label: 'Pending', apiTab: 'placed', countKey: 'placed' },
  { id: 'accepted', label: 'Accepted', apiTab: 'accepted', countKey: 'accepted' },
  { id: 'ready', label: 'Ready', apiTab: 'ready', countKey: 'ready' },
  { id: 'overdue', label: 'Overdue', countKey: 'overdue' },
  { id: 'history', label: 'History', apiTab: 'history' },
];

const EMPTY_COPY = {
  pending: 'New pre-orders will land here as customers reserve.',
  accepted: 'Orders you accept appear here until they are packed.',
  ready: 'Packed orders wait here until the shopper collects them.',
  overdue: 'Nothing is past its pickup window.',
  history: 'Completed, declined and cancelled orders show up here.',
};

function OrderNotes({ order }) {
  const notes = [];
  if (order.has_pending_change) notes.push('The shopper asked to change this order');
  if (order.stock_warning) notes.push('Your current stock cannot cover every item');
  if (order.is_expiring_soon) notes.push('Pickup starts soon: accept or decline now');
  if (notes.length === 0) return null;
  return <p className="page-primitive__danger-sm">{notes.join(' · ')}</p>;
}

OrderNotes.propTypes = { order: PropTypes.object.isRequired };

function OrderRows({ query, emptyDescription, searchTerm, onClearSearch }) {
  if (query.isPending) return <PageSkeleton />;
  if (query.isError && !query.data) {
    return <EmptyState title="Orders couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()} />;
  }
  if (query.data.orders.length === 0) {
    return searchTerm ? (
      <EmptyState
        title="No orders match your search"
        description={`Nothing found for "${searchTerm}".`}
        actionLabel="Clear search"
        onAction={onClearSearch}
      />
    ) : (
      <EmptyState title="No orders in this view" description={emptyDescription} />
    );
  }

  return (
    <>
      {query.data.orders.map((order) => (
        <div key={order.id} className="page-primitive__row-card-responsive">
          <div>
            <Link to={ROUTES.FARMER.ORDER(order.id)} className="page-primitive__semibold page-primitive__link-underline">
              #{order.id} · {order.customer.full_name}
            </Link>
            <p className="page-primitive__muted-sm">
              {order.market.name} · {formatPickupWindow(order.pickup_start_at, order.pickup_end_at)} ·{' '}
              {formatMoney(order.total_amount)}
            </p>
            <OrderNotes order={order} />
          </div>
          <div className="page-primitive__actions-row">
            <StatusBadge status={order.status} />
            <FarmerOrderActions order={order} />
          </div>
        </div>
      ))}
      {query.hasNextPage ? (
        <div className="page-primitive__justify-center-row">
          <Button
            variant="outline"
            size="sm"
            loading={query.isFetchingNextPage}
            onClick={() => query.fetchNextPage()}
          >
            Load more
          </Button>
        </div>
      ) : null}
    </>
  );
}

OrderRows.propTypes = {
  query: PropTypes.object.isRequired,
  emptyDescription: PropTypes.string.isRequired,
  searchTerm: PropTypes.string,
  onClearSearch: PropTypes.func.isRequired,
};

function PickingList({ pickupDate, onPickupDateChange }) {
  const pickingQuery = usePickingList(pickupDate);
  const rows = pickingQuery.data ?? [];

  let body;
  if (pickingQuery.isPending) body = <PageSkeleton />;
  else if (pickingQuery.isError && !pickingQuery.data) {
    body = (
      <EmptyState title="The prep list couldn't be loaded" actionLabel="Try again" onAction={() => pickingQuery.refetch()} />
    );
  } else if (rows.length === 0) {
    body = <EmptyState title="Nothing to prep for this day" description="Accepted and ready orders for this date show here." />;
  } else {
    body = (
      <div className="page-primitive__table-wrap" aria-busy={pickingQuery.isFetching}>
        <table className="page-primitive__table">
          <thead className="page-primitive__table-head-60">
            <tr>
              <th className="page-primitive__table-th">Product</th>
              <th className="page-primitive__table-th">Quantity</th>
              <th className="page-primitive__table-th">Unit</th>
              <th className="page-primitive__table-th">Orders</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.product_id}-${row.unit}`} className="page-primitive__table-row">
                <td className="page-primitive__table-td page-primitive__font-medium">{row.product_name}</td>
                <td className="page-primitive__table-td">{row.total_quantity}</td>
                <td className="page-primitive__table-td">{unitLabel(row.unit)}</td>
                <td className="page-primitive__table-td">{row.order_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="farmer-orders-page__picking">
      <div className="page-primitive__inline-row-end">
        <Input
          type="date"
          label="Pickup date"
          value={pickupDate}
          onChange={(event) => onPickupDateChange(event.target.value)}
          className="page-primitive__input-auto"
        />
        <Button size="sm" variant="outline" onClick={() => window.print()} disabled={rows.length === 0}>
          <Printer className="farmer-orders-page__print-icon" /> Print
        </Button>
      </div>
      {body}
    </div>
  );
}

PickingList.propTypes = {
  pickupDate: PropTypes.string.isRequired,
  onPickupDateChange: PropTypes.func.isRequired,
};

export default function FarmerOrdersPage() {
  const { filters, setFilters } = useUrlFilters({ view: 'orders', tab: 'pending', date: '', prep: toApiDate() });
  const search = useDebouncedSearchParam('q');

  const activeTab = TABS.find((tab) => tab.id === filters.tab) ?? TABS[0];
  const showOrders = filters.view !== 'picking';
  const isOverdue = activeTab.id === 'overdue';

  
  const listFilters = {
    q: search.term || undefined,
    pickup_from: filters.date || undefined,
    pickup_to: filters.date || undefined,
  };
  const tabQuery = useFarmerOrderList({ ...listFilters, tab: activeTab.apiTab }, { enabled: showOrders && !isOverdue });
  const overdueQuery = useFarmerOverdueOrders(listFilters, { enabled: showOrders && isOverdue });
  const ordersQuery = isOverdue ? overdueQuery : tabQuery;
  const countsQuery = useFarmerOrderTabCounts();

  return (
    <div className="farmer-orders-page">
      <PageHeader
        title="Pickup orders"
        description="Accept requests, prep bags, and complete stall collections."
        actions={
          <div className="page-primitive__actions-row">
            <Button size="sm" variant={showOrders ? 'default' : 'outline'} onClick={() => setFilters({ view: 'orders' })}>
              Order list
            </Button>
            <Button size="sm" variant={showOrders ? 'outline' : 'default'} onClick={() => setFilters({ view: 'picking' })}>
              Picking list
            </Button>
          </div>
        }
      />

      {showOrders ? (
        <>
          <form className="page-primitive__actions-row" role="search" onSubmit={(event) => event.preventDefault()}>
            <Input
              type="search"
              label="Search customer or order #"
              value={search.value}
              onChange={search.onChange}
              onKeyDown={search.onKeyDown}
              className="page-primitive__input-narrow"
            />
            <Input
              type="date"
              label="Pickup date"
              value={filters.date}
              onChange={(event) => setFilters({ date: event.target.value })}
              className="page-primitive__input-auto"
            />
          </form>

          <Tabs value={activeTab.id} onValueChange={(tab) => setFilters({ tab })}>
            <TabsList className="page-primitive__tabs-list-wrap">
              {TABS.map((tab) => {
                const count = tab.countKey ? countsQuery.data?.[tab.countKey] : undefined;
                return (
                  <TabsTrigger key={tab.id} value={tab.id}>
                    {tab.label}
                    {count !== undefined ? <span className="page-primitive__tab-badge">{count}</span> : null}
                  </TabsTrigger>
                );
              })}
            </TabsList>
            <TabsContent value={activeTab.id} className="farmer-orders-page__tab-list" aria-busy={ordersQuery.isFetching}>
              <OrderRows
                query={ordersQuery}
                emptyDescription={EMPTY_COPY[activeTab.id]}
                searchTerm={search.term}
                onClearSearch={search.clear}
              />
            </TabsContent>
          </Tabs>
        </>
      ) : (
        <PickingList pickupDate={filters.prep} onPickupDateChange={(prep) => setFilters({ prep })} />
      )}
    </div>
  );
}
