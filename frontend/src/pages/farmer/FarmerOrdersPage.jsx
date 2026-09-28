import { useMemo } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { Printer } from 'lucide-react';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { PageStatus, Pagination } from '../../components/common/Pagination';
import { StatusBadge } from '../../components/common/StatusBadge';
import { FarmerOrderActions } from '../../components/farmer/FarmerOrderActions';
import { FarmerOrderFilters, MarketFilter } from '../../components/farmer/FarmerOrderFilters';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/Tabs';
import { ROUTES } from '../../constants/routes';
import { useDebouncedSearchParam } from '../../hooks/common/useDebouncedSearchParam';
import { useUrlFilters } from '../../hooks/common/useUrlFilters';
import { readPage, usePageParam } from '../../hooks/common/usePageParam';
import {
  useFarmerOrderList,
  useFarmerOrderTabCounts,
  useFarmerOverdueOrders,
  useOrdersByCustomer,
  usePickingList,
} from '../../hooks/queries/farmer/useFarmerOrders';
import { useFarmerMarkets } from '../../hooks/queries/farmer/useFarmerMarkets';
import { useFarmerProfile } from '../../hooks/queries/farmer/useFarmerProfile';
import { usePublicConfig } from '../../hooks/queries/guest/usePublicCatalog';
import { formatDate, formatMoney, formatPickupWindow, formatTime, toApiDate } from '../../utils/formatters';
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
  if (notes.length === 0) return null;
  return <p className="page-primitive__danger-sm">{notes.join(' · ')}</p>;
}

OrderNotes.propTypes = { order: PropTypes.object.isRequired };

function OrderRows({ query, emptyDescription, hasFilters, onClearFilters, onPageChange, showStatus = true }) {
  if (query.isPending) return <PageSkeleton />;
  if (query.isError && !query.data) {
    return <EmptyState title="Orders couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()} />;
  }
  if (query.data.orders.length === 0) {
    return hasFilters ? (
      <EmptyState
        title="No orders match your filters"
        description="Try another date range, market or search."
        actionLabel="Clear filters"
        onAction={onClearFilters}
      />
    ) : (
      <EmptyState title="No orders in this view" description={emptyDescription} />
    );
  }

  return (
    <>
      {showStatus ? (
        <PageStatus
          page={query.data.page}
          pageSize={query.data.pageSize}
          total={query.data.total}
          shown={query.data.orders.length}
        />
      ) : null}
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
            {order.is_expiring_soon ? (
              <Badge variant="danger">Expires at {formatTime(order.pickup_start_at)}</Badge>
            ) : null}
            <StatusBadge status={order.status} />
            <FarmerOrderActions order={order} />
          </div>
        </div>
      ))}
      <Pagination
        page={query.data.page}
        totalPages={query.data.totalPages}
        disabled={query.isPlaceholderData}
        onChange={onPageChange}
      />
    </>
  );
}

OrderRows.propTypes = {
  query: PropTypes.object.isRequired,
  emptyDescription: PropTypes.string.isRequired,
  hasFilters: PropTypes.bool.isRequired,
  onPageChange: PropTypes.func.isRequired,
  showStatus: PropTypes.bool,
  onClearFilters: PropTypes.func.isRequired,
};

function PickingList({ pickupDate, onPickupDateChange, marketId, markets, onMarketChange }) {
  const pickingQuery = usePickingList(pickupDate, { marketId });
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
        <MarketFilter markets={markets} value={marketId} onChange={onMarketChange} />
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
  marketId: PropTypes.number.isRequired,
  markets: PropTypes.array.isRequired,
  onMarketChange: PropTypes.func.isRequired,
};

function BagsByCustomer({ pickupDate, marketId }) {
  const query = useOrdersByCustomer(pickupDate, { marketId });
  const groups = query.data ?? [];

  let body;
  if (query.isPending) body = <PageSkeleton />;
  else if (query.isError && !query.data) {
    body = <EmptyState title="Bags couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()} />;
  } else if (groups.length === 0) {
    body = <p className="page-primitive__muted-sm">No accepted or ready orders for this day.</p>;
  } else {
    body = (
      <ul className="page-primitive__stack-2" aria-busy={query.isFetching}>
        {groups.map((group) => (
          <li key={group.customer_id} className="page-primitive__row-card-responsive">
            <div>
              <p className="page-primitive__semibold">
                {group.order_count > 1
                  ? `${group.order_count} orders from ${group.customer_name} for ${formatDate(group.pickup_date)}`
                  : `${group.customer_name} · ${formatDate(group.pickup_date)}`}
              </p>
              <p className="page-primitive__muted-sm">
                {group.customer_phone ? `${group.customer_phone} · ` : ''}
                {formatMoney(group.total_amount)}
              </p>
            </div>
            <ul className="page-primitive__actions-row">
              {group.orders.map((order) => (
                <li key={order.order_id} className="page-primitive__inline-row">
                  <Link
                    to={ROUTES.FARMER.ORDER(order.order_id)}
                    className="page-primitive__link-underline page-primitive__font-medium"
                  >
                    #{order.order_id}
                  </Link>
                  <StatusBadge status={order.status} />
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <section className="farmer-orders-page__picking" aria-labelledby="bags-by-customer-title">
      <h2 className="page-primitive__heading" id="bags-by-customer-title">
        Bags by customer
      </h2>
      {body}
    </section>
  );
}

BagsByCustomer.propTypes = { pickupDate: PropTypes.string.isRequired, marketId: PropTypes.number.isRequired };

const DEFAULT_BOOKING_HORIZON_DAYS = 7;

function busiestTab(counts) {
  if (!counts) return 'pending';
  if (counts.placed > 0) return 'pending';
  if (counts.accepted > 0) return 'accepted';
  if (counts.ready > 0) return 'ready';
  return 'pending';
}

const TAB_ONLY_RESET = { changed: false, status: '', sort: '' };

const dateGroup = (tabId) => (tabId === 'history' ? 'past' : 'upcoming');

export default function FarmerOrdersPage() {
  const { filters, setFilters } = useUrlFilters({
    view: 'orders',
    tab: '',
    from: '',
    to: '',
    market: 0,
    status: '',
    sort: '',
    prep: toApiDate(),
    changed: false,
    page: 1,
  });
  const search = useDebouncedSearchParam('q');
  const countsQuery = useFarmerOrderTabCounts({ marketId: filters.market });
  const marketsQuery = useFarmerMarkets();
  const profileQuery = useFarmerProfile();
  const configQuery = usePublicConfig();
  const markets = useMemo(
    () => (marketsQuery.data ?? []).map((item) => ({ id: item.market.id, name: item.market.name })),
    [marketsQuery.data],
  );

  const explicitTab = TABS.find((tab) => tab.id === filters.tab);
  const activeTab = explicitTab ?? TABS.find((tab) => tab.id === busiestTab(countsQuery.data));
  const tabResolved = Boolean(explicitTab) || !countsQuery.isPending;
  const showOrders = filters.view !== 'picking';
  const isOverdue = activeTab.id === 'overdue';
  const onlyChanged = activeTab.id === 'accepted' && filters.changed;
  const status = activeTab.id === 'history' ? filters.status : '';
  const sort = activeTab.id === 'pending' ? filters.sort : '';
  const from = isOverdue ? '' : filters.from;
  const to = isOverdue ? '' : filters.to;

  const listFilters = {
    q: search.term || undefined,
    pickup_from: from || undefined,
    pickup_to: to || undefined,
    market_id: filters.market || undefined,
    page: readPage(filters),
  };
  const tabQuery = useFarmerOrderList(
    {
      ...listFilters,
      tab: activeTab.apiTab,
      status: status || undefined,
      ordering: sort || undefined,
      change_requested: onlyChanged || undefined,
    },
    { enabled: showOrders && tabResolved && !isOverdue },
  );
  const overdueQuery = useFarmerOverdueOrders(listFilters, { enabled: showOrders && tabResolved && isOverdue });
  const ordersQuery = isOverdue ? overdueQuery : tabQuery;
  const goToPage = usePageParam({ filters, setFilters, query: ordersQuery });

  const activeCount = [search.term, from || to, filters.market, status, sort, onlyChanged].filter(Boolean).length;

  const clearFilters = () => {
    search.clear();
    setFilters({ from: '', to: '', market: 0, ...TAB_ONLY_RESET });
  };

  const changeTab = (tab) => {
    const dateReset = dateGroup(tab) === dateGroup(activeTab.id) ? {} : { from: '', to: '' };
    setFilters({ tab, ...TAB_ONLY_RESET, ...dateReset });
  };

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
          <FarmerOrderFilters
            search={search}
            filters={{ from, to, market: filters.market, status, sort }}
            setFilters={setFilters}
            tabId={activeTab.id}
            markets={markets}
            horizonDays={configQuery.data?.booking_horizon_days ?? DEFAULT_BOOKING_HORIZON_DAYS}
            operatingDays={profileQuery.data?.operating_days ?? null}
            counts={countsQuery.data}
            activeCount={activeCount}
            onClear={clearFilters}
          />

          <Tabs value={activeTab.id} onValueChange={changeTab}>
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
              {activeTab.id === 'accepted' ? (
                <div className="page-primitive__actions-row" role="group" aria-label="Show">
                  <Button
                    size="sm"
                    variant={onlyChanged ? 'outline' : 'default'}
                    aria-pressed={!onlyChanged}
                    onClick={() => setFilters({ changed: false })}
                  >
                    All accepted
                  </Button>
                  <Button
                    size="sm"
                    variant={onlyChanged ? 'default' : 'outline'}
                    aria-pressed={onlyChanged}
                    onClick={() => setFilters({ changed: true })}
                  >
                    Change requested
                    {countsQuery.data ? (
                      <span className="page-primitive__tab-badge">{countsQuery.data.change_requests ?? 0}</span>
                    ) : null}
                  </Button>
                </div>
              ) : null}
              {tabResolved ? (
                <OrderRows
                  query={ordersQuery}
                  emptyDescription={EMPTY_COPY[activeTab.id]}
                  hasFilters={activeCount > 0}
                  onClearFilters={clearFilters}
                  onPageChange={goToPage}
                  showStatus={!isOverdue}
                />
              ) : (
                <PageSkeleton />
              )}
            </TabsContent>
          </Tabs>
        </>
      ) : (
        <>
          <PickingList
            pickupDate={filters.prep}
            onPickupDateChange={(prep) => setFilters({ prep })}
            marketId={filters.market}
            markets={markets}
            onMarketChange={(market) => setFilters({ market })}
          />
          <BagsByCustomer pickupDate={filters.prep} marketId={filters.market} />
        </>
      )}
    </div>
  );
}
