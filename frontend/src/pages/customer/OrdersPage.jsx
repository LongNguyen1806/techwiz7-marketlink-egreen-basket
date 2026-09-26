import { Link, useSearchParams } from 'react-router-dom';
import { Countdown } from '../../components/common/Countdown';
import { DataTable } from '../../components/common/table/DataTable';
import { PageHeader } from '../../components/common/PageHeader';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Badge } from '../../components/ui/Badge';
import { Tabs, TabsList, TabsTrigger } from '../../components/ui/Tabs';
import { OrderActions } from '../../components/customer/orders/OrderActions';
import { useCustomerOrders } from '../../hooks/queries/customer/useCustomerOrders';
import { useReorder } from '../../hooks/queries/customer/useReorder';
import { formatDate, formatMoney, formatTime } from '../../utils/formatters';
import '../../styles/customer/OrdersPage.css';


const STATUSES = {
  open: [
    { value: 'PLACED', label: 'Placed' },
    { value: 'ACCEPTED', label: 'Accepted' },
    { value: 'READY_FOR_PICKUP', label: 'Ready for pickup' },
  ],
  history: [
    { value: 'COMPLETED', label: 'Completed' },
    { value: 'CANCELLED', label: 'Cancelled' },
    { value: 'DECLINED', label: 'Declined' },
    { value: 'NO_SHOW', label: 'No-show' },
    { value: 'EXPIRED', label: 'Expired' },
  ],
};


export default function OrdersPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const reorder = useReorder();

  const tab = searchParams.get('tab') === 'history' ? 'history' : 'open';
  const selected = (searchParams.get('status') ?? '').split(',').filter(Boolean);
  const params = {
    tab,
    ...(selected.length ? { status: selected.join(',') } : {}),
    
    ordering: tab === 'open' ? 'pickup_start_at' : '-created_at',
  };
  const { data, isLoading } = useCustomerOrders(params);

  function switchTab(next) {
    
    setSearchParams(next === 'open' ? {} : { tab: next });
  }

  function toggleStatus(value) {
    const next = selected.includes(value)
      ? selected.filter((status) => status !== value)
      : [...selected, value];
    const query = {};
    if (tab === 'history') query.tab = tab;
    if (next.length) query.status = next.join(',');
    setSearchParams(query);
  }

  const columns = [
    {
      key: 'id',
      header: 'Order',
      render: (order) => (
        <Link to={`/customer/orders/${order.id}`} className="orders-page__id">{`#${order.id}`}</Link>
      ),
    },
    { key: 'farmer', header: 'Stall', render: (order) => order.farmer.stall_name },
    {
      key: 'market',
      header: 'Pickup at',
      render: (order) => (
        <span className="orders-page__market">
          {order.market.name}
          {order.stall_label ? <span className="orders-page__stall-label">{order.stall_label}</span> : null}
        </span>
      ),
    },
    {
      key: 'pickup',
      header: 'When',
      render: (order) => (
        `${formatDate(order.pickup_date)} · ${formatTime(order.pickup_start_at)}–${formatTime(order.pickup_end_at)}`
      ),
    },
    { key: 'item_count', header: 'Items' },
    { key: 'total_amount', header: 'Total', align: 'end', render: (order) => formatMoney(order.total_amount) },
    {
      key: 'status',
      header: 'Status',
      render: (order) => (
        <span className="orders-page__status">
          <StatusBadge status={order.status} />
          {order.has_pending_change ? <Badge variant="warning">Change requested</Badge> : null}
          {order.is_expiring_soon ? <Badge variant="warning">Pickup soon</Badge> : null}
        </span>
      ),
    },
    {
      key: 'cutoff',
      header: 'Deadline',
      render: (order) => (
        
        (order.allowed_actions ?? ['MODIFY']).length > 0 || tab === 'open'
          ? <Countdown targetIso={order.cutoff_at} label="Edit/cancel until" />
          : null
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (order) => (
        <OrderActions
          order={order}
          onReorder={(row) => reorder.mutate(row.id)}
          reorderPending={reorder.isPending}
        />
      ),
    },
  ];

  return (
    <section className="orders-page">
      <PageHeader title="My orders" description="One order per stall, paid in cash when you collect." />

      <Tabs value={tab} onValueChange={switchTab}>
        <TabsList>
          <TabsTrigger value="open">Open</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>
      </Tabs>

      <fieldset className="orders-page__filters">
        <legend className="orders-page__filters-legend">Status</legend>
        {STATUSES[tab].map((status) => (
          <label className="orders-page__filter" key={status.value}>
            <input
              type="checkbox"
              className="orders-page__filter-input"
              checked={selected.includes(status.value)}
              onChange={() => toggleStatus(status.value)}
            />
            <span className="orders-page__filter-text">{status.label}</span>
          </label>
        ))}
      </fieldset>

      <DataTable
        columns={columns}
        rows={data?.results ?? []}
        rowKey={(order) => order.id}
        caption="My orders"
        isLoading={isLoading}
        emptyMessage="No orders here yet."
      />
    </section>
  );
}
